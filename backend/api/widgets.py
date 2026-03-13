"""
Widget configuration CRUD — PostgreSQL-backed.
Manages dashboard pages, widgets, cached data, and data sources.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import widget_store

router = APIRouter()


# --- Pydantic models (same shape as before for frontend compatibility) ---

class WidgetConfig(BaseModel):
    id: str | None = None
    type: str
    title: str
    x: int = 0
    y: int = 0
    w: int = 6
    h: int = 8
    props: dict = {}
    mdx: str | None = None
    data: Any | None = None
    data_source: dict | None = None
    refresh_seconds: int = 30


class OverviewPage(BaseModel):
    id: str | None = None
    name: str
    widgets: list[dict] = []
    is_default: bool = False


# --- Widget CRUD (legacy global widgets — for chat pinning) ---

@router.get("/")
async def list_widgets():
    # Return all widgets across all pages (flat list)
    pages = widget_store.list_pages()
    all_widgets = []
    for p in pages:
        all_widgets.extend(p.get("widgets", []))
    return {"widgets": all_widgets, "count": len(all_widgets)}


@router.post("/")
async def create_widget_global(config: WidgetConfig):
    """Create a widget (used by chat pinning). Adds to the default page."""
    pages = widget_store.list_pages()
    target_page_id = None
    for p in pages:
        if p.get("is_default"):
            target_page_id = p["id"]
            break
    if not target_page_id and pages:
        target_page_id = pages[0]["id"]
    if not target_page_id:
        # Create a default page
        new_page = widget_store.create_page("Dashboard", is_default=True)
        target_page_id = new_page["id"]

    widget = config.model_dump()
    widget = widget_store.create_widget(target_page_id, widget)
    return {"status": "created", "widget": widget}


@router.put("/{widget_id}")
async def update_widget(widget_id: str, config: WidgetConfig):
    # For now, delete and recreate (simple approach)
    widget_store.delete_widget(widget_id)
    pages = widget_store.list_pages()
    target_page_id = pages[0]["id"] if pages else None
    if not target_page_id:
        raise HTTPException(404, "No pages exist")
    widget = config.model_dump()
    widget["id"] = widget_id
    widget = widget_store.create_widget(target_page_id, widget)
    return {"status": "updated", "widget": widget}


@router.delete("/{widget_id}")
async def delete_widget(widget_id: str):
    if not widget_store.delete_widget(widget_id):
        raise HTTPException(404, f"Widget {widget_id} not found")
    return {"status": "deleted", "widget_id": widget_id}


# --- Overview pages ---

@router.get("/pages")
async def list_pages():
    pages = widget_store.list_pages()
    return {"pages": pages}


@router.get("/pages/{page_id}")
async def get_page(page_id: str):
    page = widget_store.get_page(page_id)
    if not page:
        raise HTTPException(404, f"Page '{page_id}' not found")
    return page


@router.post("/pages")
async def create_page(page: OverviewPage):
    pages = widget_store.list_pages()
    is_default = page.is_default or len(pages) == 0
    result = widget_store.create_page(page.name, is_default=is_default)
    return {"status": "created", "page": result}


@router.put("/pages/{page_id}")
async def update_page(page_id: str, page: OverviewPage):
    result = widget_store.update_page(
        page_id,
        name=page.name,
        is_default=page.is_default if page.is_default else None,
        widgets=page.widgets,
    )
    if not result:
        raise HTTPException(404, f"Page '{page_id}' not found")
    return {"status": "updated", "page": result}


@router.delete("/pages/{page_id}")
async def delete_page(page_id: str):
    if not widget_store.delete_page(page_id):
        raise HTTPException(404, f"Page '{page_id}' not found")
    return {"status": "deleted", "page_id": page_id}


# --- Widget data (cached) ---

@router.get("/{widget_id}/data")
async def get_widget_data(widget_id: str):
    data = widget_store.get_widget_data(widget_id)
    if data is None:
        return {"data": None, "fetched_at": None, "error": None}
    return data


@router.post("/{widget_id}/refresh")
async def refresh_widget_data(widget_id: str):
    """Force refresh a widget's data from its source."""
    from refresh_engine import refresh_single_widget
    result = refresh_single_widget(widget_id)
    return result


# --- Data sources listing ---

@router.get("/datasources")
async def list_datasources():
    sources = widget_store.list_datasources()
    return {"datasources": sources, "count": len(sources)}
