"""
Widget Data Refresh Engine — background service that keeps widget data fresh.

Runs as an asyncio task, checking every 30 seconds for widgets that need a data refresh.
Fetches data from the appropriate source (TM1 MDX, TM1 cell, PostgreSQL, AI prompt)
and caches the result in agent_rag.widget_data.
"""
from __future__ import annotations

import asyncio
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from logger import log
import widget_store

_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="refresh")
_running = False


# ---------------------------------------------------------------------------
#  Data fetchers by source type
# ---------------------------------------------------------------------------

def _fetch_mdx(data_source: dict, props: dict) -> dict:
    """Execute an MDX query via TM1 and return {headers, rows} in tabular format."""
    query = data_source.get("query") or props.get("mdx", "")
    if not query:
        return {"error": "No MDX query defined"}

    max_rows = props.get("maxRows", 500)
    try:
        from mcp_server.skills.mcp_bridge import tm1_execute_mdx_rows
        result = tm1_execute_mdx_rows(query, max_rows)
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        # Already in tabular format {headers, rows: [[...]]}
        if isinstance(result, dict) and "headers" in result:
            return {"headers": result["headers"], "rows": result.get("rows", [])}

        # Convert dict-rows [{col:val, ...}, ...] to tabular {headers, rows: [[...]]}
        raw_rows = result.get("rows", []) if isinstance(result, dict) else []
        if raw_rows and isinstance(raw_rows[0], dict):
            headers = list(raw_rows[0].keys())
            rows = [[row.get(h) for h in headers] for row in raw_rows]
            return {"headers": headers, "rows": rows}

        return {"headers": [], "rows": []}
    except Exception as e:
        raise RuntimeError(f"MDX execution failed: {e}")


def _fetch_tm1_cell(data_source: dict, props: dict) -> dict:
    """Fetch a single TM1 cell value."""
    cube = data_source.get("cube") or props.get("cube", "")
    coordinates = data_source.get("coordinates") or props.get("coordinates", "")
    if not cube or not coordinates:
        return {"error": "Missing cube or coordinates"}

    try:
        from mcp_server.skills.mcp_bridge import tm1_get_cell_value
        result = tm1_get_cell_value(cube=cube, elements=coordinates)
        if isinstance(result, dict):
            return result
        return {"value": result}
    except Exception as e:
        raise RuntimeError(f"TM1 cell fetch failed: {e}")


def _fetch_tm1_elements(data_source: dict, props: dict) -> dict:
    """Fetch TM1 dimension elements."""
    dimension = data_source.get("dimension") or props.get("dimension") or props.get("dimensions", "")
    if not dimension:
        return {"error": "No dimension specified"}

    hierarchy = data_source.get("hierarchy") or props.get("hierarchy", "")
    try:
        from mcp_server.skills.mcp_bridge import tm1_get_dimension_elements
        result = tm1_get_dimension_elements(
            dimension_name=dimension,
            hierarchy_name=hierarchy or dimension,
            limit=props.get("limit", 1000),
        )
        return result if isinstance(result, dict) else {"elements": result}
    except Exception as e:
        raise RuntimeError(f"TM1 elements fetch failed: {e}")


def _fetch_sql(data_source: dict, props: dict) -> dict:
    """Execute a SQL query against PostgreSQL."""
    query = data_source.get("query") or props.get("initialSql", "")
    if not query:
        return {"error": "No SQL query defined"}

    database = data_source.get("database", "financials")
    try:
        from mcp_server.skills.mcp_bridge import pg_query_financials
        result = pg_query_financials(sql=query, database=database, limit=500)
        if isinstance(result, dict) and "columns" in result:
            return {"headers": result["columns"], "rows": result.get("rows", [])}
        return result if isinstance(result, dict) else {"raw": result}
    except Exception as e:
        raise RuntimeError(f"SQL execution failed: {e}")


def _fetch_ai_prompt(data_source: dict, props: dict) -> dict:
    """Execute an AI prompt and return the result."""
    prompt = data_source.get("prompt", "")
    if not prompt:
        return {"error": "No AI prompt defined"}

    try:
        from core import run_agent
        response_text, tool_calls = run_agent(prompt, messages=[])
        return {"response": response_text, "tool_calls_count": len(tool_calls)}
    except Exception as e:
        raise RuntimeError(f"AI prompt execution failed: {e}")


_FETCHERS = {
    "mdx": _fetch_mdx,
    "tm1_cell": _fetch_tm1_cell,
    "tm1_elements": _fetch_tm1_elements,
    "sql": _fetch_sql,
    "ai_prompt": _fetch_ai_prompt,
}


# ---------------------------------------------------------------------------
#  Refresh logic
# ---------------------------------------------------------------------------

def _refresh_widget(widget: dict) -> dict:
    """Refresh a single widget's data. Returns {data, error}."""
    ds = widget.get("data_source", {})
    if isinstance(ds, str):
        ds = json.loads(ds)
    source_type = ds.get("type", "static")

    if source_type in ("static", "paw"):
        return {"data": None, "error": None, "skipped": True}

    props = widget.get("props", {})
    if isinstance(props, str):
        props = json.loads(props)

    fetcher = _FETCHERS.get(source_type)
    if not fetcher:
        return {"data": None, "error": f"Unknown source type: {source_type}"}

    t0 = time.monotonic()
    try:
        data = fetcher(ds, props)
        duration = int((time.monotonic() - t0) * 1000)
        log.info("Widget %s refreshed (%s, %dms)", widget["id"], source_type, duration,
                 extra={"widget_id": widget["id"], "source_type": source_type, "duration_ms": duration})
        return {"data": data, "error": None}
    except Exception as e:
        duration = int((time.monotonic() - t0) * 1000)
        log.warning("Widget %s refresh failed (%s, %dms): %s",
                    widget["id"], source_type, duration, e,
                    extra={"widget_id": widget["id"], "source_type": source_type, "duration_ms": duration})
        return {"data": None, "error": str(e)}


def refresh_single_widget(widget_id: str) -> dict:
    """Force refresh a single widget by ID. Returns the updated data."""
    from widget_store import get_widgets_needing_refresh, save_widget_data, get_widget_data
    import psycopg2
    import psycopg2.extras
    from config import settings

    # Fetch the widget directly
    conn = psycopg2.connect(
        host=settings.pg_bi_host, port=settings.pg_bi_port,
        dbname=settings.pg_bi_db, user=settings.pg_bi_user,
        password=settings.pg_bi_password,
    )
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f"""
            SELECT id, type, props, data_source, refresh_seconds
            FROM {settings.rag_schema}.widgets WHERE id = %s
        """, (widget_id,))
        row = cur.fetchone()
    conn.close()

    if not row:
        return {"error": f"Widget {widget_id} not found", "data": None}

    widget = dict(row)
    result = _refresh_widget(widget)

    if result.get("skipped"):
        cached = get_widget_data(widget_id)
        return cached or {"data": None, "fetched_at": None, "error": None}

    if result["data"] is not None:
        save_widget_data(widget_id, result["data"], error=None)
    elif result["error"]:
        save_widget_data(widget_id, {}, error=result["error"])

    return get_widget_data(widget_id) or {"data": None, "fetched_at": None, "error": result.get("error")}


# ---------------------------------------------------------------------------
#  Background refresh loop
# ---------------------------------------------------------------------------

async def refresh_loop(interval: int = 30):
    """Background task: refresh all stale widget data every `interval` seconds."""
    global _running
    _running = True
    log.info("Refresh engine started (interval=%ds)", interval)

    # Initial delay to let the app start up
    await asyncio.sleep(5)

    loop = asyncio.get_event_loop()

    while _running:
        try:
            widgets = widget_store.get_widgets_needing_refresh()
            if widgets:
                log.info("Refreshing %d widgets", len(widgets))
                for widget in widgets:
                    try:
                        result = await loop.run_in_executor(_executor, _refresh_widget, widget)
                        if result.get("skipped"):
                            continue
                        if result["data"] is not None:
                            widget_store.save_widget_data(widget["id"], result["data"])
                        elif result["error"]:
                            widget_store.save_widget_data(widget["id"], {}, error=result["error"])
                    except Exception:
                        log.debug("Refresh failed for widget %s", widget.get("id"), exc_info=True)
        except Exception:
            log.debug("Refresh loop error", exc_info=True)

        await asyncio.sleep(interval)


def stop():
    """Stop the refresh loop."""
    global _running
    _running = False
