"""
Widget Store — PostgreSQL-backed storage for dashboard pages, widgets, and cached data.

Replaces the old YAML-based widget_configs.yaml with proper DB persistence.
Tables live in the configured rag_schema (default: agent_rag).

Data source types:
  - mdx:          TM1 MDX query → {headers, rows}
  - tm1_cell:     Single TM1 cell value → {value, formatted}
  - tm1_elements: TM1 dimension elements → {elements}
  - sql:          PostgreSQL query → {headers, rows}
  - ai_prompt:    Natural language prompt executed by AI → {headers, rows} or {value}
  - paw:          PAW iframe embed — no cached data
  - static:       Inline data, no refresh
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras

from config import settings
from logger import log

_SCHEMA = settings.rag_schema


# ---------------------------------------------------------------------------
#  Connection helper (uses same pattern as context_store.py)
# ---------------------------------------------------------------------------

def _get_conn():
    return psycopg2.connect(
        host=settings.pg_bi_host, port=settings.pg_bi_port,
        dbname=settings.pg_bi_db, user=settings.pg_bi_user,
        password=settings.pg_bi_password,
    )


# ---------------------------------------------------------------------------
#  Schema creation
# ---------------------------------------------------------------------------

def ensure_tables() -> None:
    """Create widget tables if they don't exist."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_SCHEMA}.dashboard_pages (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                is_default  BOOLEAN DEFAULT FALSE,
                layout      JSONB DEFAULT '{{}}'::jsonb,
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_SCHEMA}.widgets (
                id               TEXT PRIMARY KEY,
                page_id          TEXT REFERENCES {_SCHEMA}.dashboard_pages(id) ON DELETE CASCADE,
                type             TEXT NOT NULL,
                title            TEXT NOT NULL,
                x                INT DEFAULT 0,
                y                INT DEFAULT 0,
                w                INT DEFAULT 6,
                h                INT DEFAULT 8,
                props            JSONB DEFAULT '{{}}'::jsonb,
                data_source      JSONB DEFAULT '{{}}'::jsonb,
                refresh_seconds  INT DEFAULT 30,
                sort_order       INT DEFAULT 0,
                created_at       TIMESTAMPTZ DEFAULT NOW(),
                updated_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_SCHEMA}.widget_data (
                widget_id   TEXT PRIMARY KEY REFERENCES {_SCHEMA}.widgets(id) ON DELETE CASCADE,
                data        JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                fetched_at  TIMESTAMPTZ DEFAULT NOW(),
                error       TEXT,
                stale       BOOLEAN DEFAULT FALSE
            )
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_widgets_page
            ON {_SCHEMA}.widgets(page_id)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_widget_data_stale
            ON {_SCHEMA}.widget_data(stale) WHERE stale = TRUE
        """)
    conn.commit()
    conn.close()
    log.info("Widget store tables ensured")


# ---------------------------------------------------------------------------
#  YAML → DB migration
# ---------------------------------------------------------------------------

def migrate_from_yaml(yaml_path: str) -> int:
    """One-time migration: read widget_configs.yaml and insert into DB.
    Returns the number of widgets migrated. Skips if DB already has pages.
    """
    import yaml
    from pathlib import Path

    path = Path(yaml_path)
    if not path.exists():
        return 0

    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {_SCHEMA}.dashboard_pages")
        if cur.fetchone()[0] > 0:
            conn.close()
            return 0  # Already have data, skip migration

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    pages = data.get("pages", [])
    widgets_global = data.get("widgets", [])
    count = 0

    with conn.cursor() as cur:
        for page in pages:
            page_id = page.get("id", f"page_{uuid.uuid4().hex[:8]}")
            cur.execute(
                f"""INSERT INTO {_SCHEMA}.dashboard_pages (id, name, is_default)
                    VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                (page_id, page.get("name", "Untitled"), page.get("is_default", False)),
            )
            for w in page.get("widgets", []):
                _insert_widget(cur, w, page_id)
                count += 1

        # Global widgets (legacy) → put on first page or create one
        if widgets_global:
            cur.execute(f"SELECT id FROM {_SCHEMA}.dashboard_pages LIMIT 1")
            row = cur.fetchone()
            if row:
                target_page = row[0]
            else:
                target_page = f"page_{uuid.uuid4().hex[:8]}"
                cur.execute(
                    f"""INSERT INTO {_SCHEMA}.dashboard_pages (id, name, is_default)
                        VALUES (%s, %s, TRUE)""",
                    (target_page, "Dashboard"),
                )
            for w in widgets_global:
                _insert_widget(cur, w, target_page)
                count += 1

    conn.commit()
    conn.close()
    log.info("Migrated %d widgets from YAML to DB", count)
    return count


# Width/height mapping from old YAML format to grid units
_WIDTH_MAP = {1: 3, 2: 6, 3: 9, 4: 12}
_HEIGHT_MAP = {"sm": 4, "md": 8, "lg": 12}


def _insert_widget(cur, w: dict, page_id: str) -> None:
    """Insert a single widget dict into the DB, normalizing old format."""
    widget_id = w.get("id", f"w_{uuid.uuid4().hex[:8]}")
    wtype = w.get("type", "CubeViewer")
    title = w.get("title", "Untitled")
    props = w.get("props", {})

    # Normalize sizes: old format uses width(1-4)/height(sm/md/lg)
    raw_w = w.get("w") or _WIDTH_MAP.get(w.get("width"), None)
    raw_h = w.get("h") or _HEIGHT_MAP.get(w.get("height"), None)
    gw = raw_w or 6
    gh = raw_h or 8
    x = w.get("x", 0)
    y = w.get("y", 0)

    data_source = w.get("data_source") or _extract_data_source(wtype, props)

    cur.execute(
        f"""INSERT INTO {_SCHEMA}.widgets
                (id, page_id, type, title, x, y, w, h, props, data_source, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING""",
        (widget_id, page_id, wtype, title, x, y, gw, gh,
         json.dumps(props, default=str), json.dumps(data_source, default=str), 0),
    )


# ---------------------------------------------------------------------------
#  Data source extraction
# ---------------------------------------------------------------------------

def _extract_data_source(widget_type: str, props: dict) -> dict:
    """Derive data_source from widget type and props."""
    mdx = props.get("mdx")
    cube = props.get("cube")

    if widget_type in ("CubeViewer", "PivotTable", "LineChart", "BarChart", "PieChart"):
        if mdx:
            return {"type": "mdx", "query": mdx, "cube": cube or ""}
        if cube:
            return {"type": "mdx", "query": "", "cube": cube}
        return {"type": "static"}

    if widget_type == "KPICard":
        if cube and props.get("coordinates"):
            return {"type": "tm1_cell", "cube": cube, "coordinates": props["coordinates"]}
        return {"type": "static"}

    if widget_type in ("DimensionTree", "DimensionEditor", "DimensionSetEditor", "DimensionControl"):
        dim = props.get("dimension") or props.get("dimensions")
        if dim:
            return {"type": "tm1_elements", "dimension": dim,
                    "hierarchy": props.get("hierarchy", ""),
                    "attributes": props.get("attributes", [])}
        return {"type": "static"}

    if widget_type in ("MDXEditor",):
        return {"type": "mdx", "query": props.get("initialMdx", ""), "cube": cube or ""}

    if widget_type in ("SQLEditor",):
        return {"type": "sql", "query": props.get("initialSql", ""),
                "database": props.get("database", "financials")}

    if widget_type in ("PAWViewer", "PAWCubeViewer", "PAWDimensionEditor", "PAWBook"):
        return {"type": "paw"}

    if widget_type == "DataGrid":
        return {"type": "static"}

    return {"type": "static"}


# ---------------------------------------------------------------------------
#  Page CRUD
# ---------------------------------------------------------------------------

def list_pages() -> list[dict]:
    """Fetch all pages with their widgets and cached data."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f"""
            SELECT id, name, is_default, layout, created_at, updated_at
            FROM {_SCHEMA}.dashboard_pages
            ORDER BY is_default DESC, name
        """)
        pages = [dict(r) for r in cur.fetchall()]

        for page in pages:
            cur.execute(f"""
                SELECT w.*, d.data AS cached_data, d.fetched_at, d.error AS data_error
                FROM {_SCHEMA}.widgets w
                LEFT JOIN {_SCHEMA}.widget_data d ON w.id = d.widget_id
                WHERE w.page_id = %s
                ORDER BY w.sort_order, w.y, w.x
            """, (page["id"],))
            widgets = []
            for wr in cur.fetchall():
                wd = dict(wr)
                # Merge cached data into widget config for frontend
                widget = {
                    "id": wd["id"],
                    "type": wd["type"],
                    "title": wd["title"],
                    "x": wd["x"],
                    "y": wd["y"],
                    "w": wd["w"],
                    "h": wd["h"],
                    "props": wd["props"] if isinstance(wd["props"], dict) else json.loads(wd["props"] or "{}"),
                    "data_source": wd["data_source"] if isinstance(wd["data_source"], dict) else json.loads(wd["data_source"] or "{}"),
                    "refresh_seconds": wd["refresh_seconds"],
                    "data": wd.get("cached_data"),
                    "fetched_at": str(wd["fetched_at"]) if wd.get("fetched_at") else None,
                    "data_error": wd.get("data_error"),
                }
                widgets.append(widget)
            page["widgets"] = widgets
            # Serialize timestamps
            page["created_at"] = str(page["created_at"]) if page.get("created_at") else None
            page["updated_at"] = str(page["updated_at"]) if page.get("updated_at") else None

    conn.close()
    return pages


def get_page(page_id: str) -> dict | None:
    """Fetch a single page with widgets."""
    pages = list_pages()
    for p in pages:
        if p["id"] == page_id:
            return p
    return None


def create_page(name: str, is_default: bool = False) -> dict:
    """Create a new dashboard page."""
    page_id = f"page_{uuid.uuid4().hex[:8]}"
    conn = _get_conn()
    with conn.cursor() as cur:
        if is_default:
            cur.execute(f"UPDATE {_SCHEMA}.dashboard_pages SET is_default = FALSE")
        cur.execute(
            f"""INSERT INTO {_SCHEMA}.dashboard_pages (id, name, is_default)
                VALUES (%s, %s, %s)""",
            (page_id, name, is_default),
        )
    conn.commit()
    conn.close()
    return {"id": page_id, "name": name, "is_default": is_default, "widgets": []}


def update_page(page_id: str, name: str | None = None, is_default: bool | None = None,
                widgets: list[dict] | None = None) -> dict | None:
    """Update page metadata and/or its widgets."""
    conn = _get_conn()
    with conn.cursor() as cur:
        # Check page exists
        cur.execute(f"SELECT id FROM {_SCHEMA}.dashboard_pages WHERE id = %s", (page_id,))
        if not cur.fetchone():
            conn.close()
            return None

        if name is not None:
            cur.execute(
                f"UPDATE {_SCHEMA}.dashboard_pages SET name = %s, updated_at = NOW() WHERE id = %s",
                (name, page_id),
            )
        if is_default is not None and is_default:
            cur.execute(f"UPDATE {_SCHEMA}.dashboard_pages SET is_default = FALSE")
            cur.execute(
                f"UPDATE {_SCHEMA}.dashboard_pages SET is_default = TRUE, updated_at = NOW() WHERE id = %s",
                (page_id,),
            )

        if widgets is not None:
            # Upsert all widgets for this page
            existing_ids = set()
            cur.execute(f"SELECT id FROM {_SCHEMA}.widgets WHERE page_id = %s", (page_id,))
            existing_ids = {r[0] for r in cur.fetchall()}

            incoming_ids = set()
            for i, w in enumerate(widgets):
                wid = w.get("id", f"w_{uuid.uuid4().hex[:8]}")
                incoming_ids.add(wid)
                wtype = w.get("type", "CubeViewer")
                title = w.get("title", "Untitled")
                props = w.get("props", {})
                ds = w.get("data_source") or _extract_data_source(wtype, props)

                # Normalize sizes
                raw_w = w.get("w") or _WIDTH_MAP.get(w.get("width"), None)
                raw_h = w.get("h") or _HEIGHT_MAP.get(w.get("height"), None)
                gw = raw_w or 6
                gh = raw_h or 8

                cur.execute(f"""
                    INSERT INTO {_SCHEMA}.widgets
                        (id, page_id, type, title, x, y, w, h, props, data_source, refresh_seconds, sort_order, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        type = EXCLUDED.type,
                        title = EXCLUDED.title,
                        x = EXCLUDED.x, y = EXCLUDED.y,
                        w = EXCLUDED.w, h = EXCLUDED.h,
                        props = EXCLUDED.props,
                        data_source = EXCLUDED.data_source,
                        refresh_seconds = EXCLUDED.refresh_seconds,
                        sort_order = EXCLUDED.sort_order,
                        updated_at = NOW()
                """, (
                    wid, page_id, wtype, title,
                    w.get("x", 0), w.get("y", 0), gw, gh,
                    json.dumps(props, default=str),
                    json.dumps(ds, default=str),
                    w.get("refresh_seconds", 30),
                    i,
                ))

            # Remove widgets that are no longer in the page
            removed = existing_ids - incoming_ids
            if removed:
                cur.execute(
                    f"DELETE FROM {_SCHEMA}.widgets WHERE id = ANY(%s)",
                    (list(removed),),
                )

    conn.commit()
    conn.close()
    return get_page(page_id)


def delete_page(page_id: str) -> bool:
    """Delete a page and all its widgets (cascade). Returns True if deleted."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"SELECT is_default FROM {_SCHEMA}.dashboard_pages WHERE id = %s", (page_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        was_default = row[0]
        cur.execute(f"DELETE FROM {_SCHEMA}.dashboard_pages WHERE id = %s", (page_id,))
        if was_default:
            cur.execute(f"""
                UPDATE {_SCHEMA}.dashboard_pages SET is_default = TRUE
                WHERE id = (SELECT id FROM {_SCHEMA}.dashboard_pages ORDER BY name LIMIT 1)
            """)
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
#  Widget CRUD
# ---------------------------------------------------------------------------

def create_widget(page_id: str, widget: dict) -> dict:
    """Create a widget on a page. Returns the widget dict."""
    wid = widget.get("id", f"w_{uuid.uuid4().hex[:8]}")
    wtype = widget.get("type", "CubeViewer")
    title = widget.get("title", "Untitled")
    props = widget.get("props", {})
    ds = widget.get("data_source") or _extract_data_source(wtype, props)

    raw_w = widget.get("w") or _WIDTH_MAP.get(widget.get("width"), None)
    raw_h = widget.get("h") or _HEIGHT_MAP.get(widget.get("height"), None)
    gw = raw_w or 6
    gh = raw_h or 8

    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {_SCHEMA}.widgets
                (id, page_id, type, title, x, y, w, h, props, data_source, refresh_seconds, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                page_id = EXCLUDED.page_id,
                type = EXCLUDED.type,
                title = EXCLUDED.title,
                x = EXCLUDED.x, y = EXCLUDED.y,
                w = EXCLUDED.w, h = EXCLUDED.h,
                props = EXCLUDED.props,
                data_source = EXCLUDED.data_source,
                updated_at = NOW()
        """, (
            wid, page_id, wtype, title,
            widget.get("x", 0), widget.get("y", 0), gw, gh,
            json.dumps(props, default=str),
            json.dumps(ds, default=str),
            widget.get("refresh_seconds", 30),
            0,
        ))

        # If there's inline data (e.g. DataGrid), store it immediately
        data = widget.get("data")
        if data:
            cur.execute(f"""
                INSERT INTO {_SCHEMA}.widget_data (widget_id, data, fetched_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (widget_id) DO UPDATE SET data = EXCLUDED.data, fetched_at = NOW(), error = NULL
            """, (wid, json.dumps(data, default=str)))

    conn.commit()
    conn.close()

    return {
        "id": wid, "type": wtype, "title": title,
        "x": widget.get("x", 0), "y": widget.get("y", 0),
        "w": gw, "h": gh,
        "props": props, "data_source": ds,
        "refresh_seconds": widget.get("refresh_seconds", 30),
        "data": data,
    }


def delete_widget(widget_id: str) -> bool:
    """Delete a widget. Returns True if deleted."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {_SCHEMA}.widgets WHERE id = %s", (widget_id,))
        deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ---------------------------------------------------------------------------
#  Widget data cache
# ---------------------------------------------------------------------------

def get_widget_data(widget_id: str) -> dict | None:
    """Get cached data for a widget."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f"""
            SELECT data, fetched_at, error, stale
            FROM {_SCHEMA}.widget_data WHERE widget_id = %s
        """, (widget_id,))
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "data": row["data"],
        "fetched_at": str(row["fetched_at"]) if row["fetched_at"] else None,
        "error": row["error"],
        "stale": row["stale"],
    }


def save_widget_data(widget_id: str, data: Any, error: str | None = None) -> None:
    """Save (or update) cached data for a widget."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {_SCHEMA}.widget_data (widget_id, data, fetched_at, error, stale)
            VALUES (%s, %s, NOW(), %s, FALSE)
            ON CONFLICT (widget_id) DO UPDATE SET
                data = EXCLUDED.data,
                fetched_at = NOW(),
                error = EXCLUDED.error,
                stale = FALSE
        """, (widget_id, json.dumps(data, default=str) if data is not None else "{}", error))
    conn.commit()
    conn.close()


def mark_stale(widget_id: str) -> None:
    """Mark a widget's data as stale."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"""
            UPDATE {_SCHEMA}.widget_data SET stale = TRUE WHERE widget_id = %s
        """, (widget_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
#  Data sources listing (for Data Sources page)
# ---------------------------------------------------------------------------

def list_datasources() -> list[dict]:
    """List all widgets with their data sources and cached data status."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f"""
            SELECT w.id AS widget_id, w.type AS widget_type, w.title AS widget_title,
                   w.page_id, p.name AS page_name,
                   w.data_source, w.refresh_seconds, w.props,
                   d.fetched_at, d.error, d.stale,
                   d.data AS cached_data
            FROM {_SCHEMA}.widgets w
            LEFT JOIN {_SCHEMA}.dashboard_pages p ON w.page_id = p.id
            LEFT JOIN {_SCHEMA}.widget_data d ON w.id = d.widget_id
            ORDER BY p.name, w.sort_order, w.y, w.x
        """)
        rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        rd = dict(r)
        ds = rd["data_source"] if isinstance(rd["data_source"], dict) else json.loads(rd["data_source"] or "{}")
        cached = rd.get("cached_data")

        # Build a preview (first 3 rows if tabular)
        preview = None
        if cached and isinstance(cached, dict):
            headers = cached.get("headers", [])
            rows_data = cached.get("rows", [])
            if headers and rows_data:
                preview = {"headers": headers, "rows": rows_data[:3], "total_rows": len(rows_data)}
            elif "value" in cached:
                preview = {"value": cached["value"]}

        results.append({
            "widget_id": rd["widget_id"],
            "widget_type": rd["widget_type"],
            "widget_title": rd["widget_title"],
            "page_id": rd["page_id"],
            "page_name": rd["page_name"],
            "data_source": ds,
            "refresh_seconds": rd["refresh_seconds"],
            "fetched_at": str(rd["fetched_at"]) if rd["fetched_at"] else None,
            "error": rd["error"],
            "stale": rd.get("stale", False),
            "preview": preview,
        })

    return results


# ---------------------------------------------------------------------------
#  Widgets needing refresh (used by refresh engine)
# ---------------------------------------------------------------------------

def get_widgets_needing_refresh() -> list[dict]:
    """Get widgets whose data is stale or hasn't been fetched recently."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f"""
            SELECT w.id, w.type, w.props, w.data_source, w.refresh_seconds
            FROM {_SCHEMA}.widgets w
            LEFT JOIN {_SCHEMA}.widget_data d ON w.id = d.widget_id
            WHERE w.data_source->>'type' NOT IN ('static', 'paw')
              AND (d.fetched_at IS NULL
                   OR d.fetched_at < NOW() - (w.refresh_seconds || ' seconds')::interval)
            ORDER BY d.fetched_at NULLS FIRST
        """)
        rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
