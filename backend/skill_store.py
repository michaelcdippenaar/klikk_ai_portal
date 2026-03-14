"""
Skill Store — DB-backed skill registry.

Stores skill metadata (module name, keywords, enabled/always_on) in
agent_rag.skill_registry.  The actual Python code stays on disk;
this table controls which skills are loaded and how they are routed.

Table: agent_rag.skill_registry
  - module_name  TEXT PRIMARY KEY  (e.g. "web_search")
  - import_path  TEXT              (e.g. "mcp_server.skills.web_search")
  - display_name TEXT
  - description  TEXT
  - keywords     TEXT[]            (routing keywords)
  - always_on    BOOLEAN           (always include in tool routing)
  - enabled      BOOLEAN           (load this skill at all)
  - sort_order   INT
  - created_at / updated_at  TIMESTAMPTZ
"""
from __future__ import annotations

import threading
import time
from typing import Any

import psycopg2
import psycopg2.extras

from config import settings
from logger import log

# ---------------------------------------------------------------------------
#  Connection
# ---------------------------------------------------------------------------

def _get_conn():
    return psycopg2.connect(
        host=settings.pg_bi_host,
        port=settings.pg_bi_port,
        dbname=settings.pg_bi_db,
        user=settings.pg_bi_user,
        password=settings.pg_bi_password,
    )

_SCHEMA = settings.rag_schema  # "agent_rag"

_tables_ok = False


def ensure_tables():
    global _tables_ok
    if _tables_ok:
        return
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {_SCHEMA}.skill_registry (
                    module_name  TEXT PRIMARY KEY,
                    import_path  TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL DEFAULT '',
                    description  TEXT NOT NULL DEFAULT '',
                    keywords     TEXT[] NOT NULL DEFAULT '{{}}',
                    always_on    BOOLEAN NOT NULL DEFAULT FALSE,
                    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
                    sort_order   INT NOT NULL DEFAULT 100,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
        conn.close()
        _tables_ok = True
    except Exception:
        log.warning("skill_store: table creation failed", exc_info=True)


# ---------------------------------------------------------------------------
#  Cache
# ---------------------------------------------------------------------------
_cache: list[dict] | None = None
_cache_lock = threading.Lock()
_cache_ts: float = 0
_CACHE_TTL = 120  # seconds


def invalidate_cache():
    global _cache, _cache_ts
    with _cache_lock:
        _cache = None
        _cache_ts = 0


# ---------------------------------------------------------------------------
#  Read
# ---------------------------------------------------------------------------

def get_all_skills() -> list[dict]:
    """Return all skill rows (including disabled) from DB."""
    global _cache, _cache_ts
    with _cache_lock:
        if _cache is not None and (time.monotonic() - _cache_ts) < _CACHE_TTL:
            return list(_cache)
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT module_name, import_path, display_name, description,
                       keywords, always_on, enabled, sort_order,
                       created_at, updated_at
                FROM {_SCHEMA}.skill_registry
                ORDER BY sort_order, module_name
            """)
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        with _cache_lock:
            _cache = rows
            _cache_ts = time.monotonic()
        return list(rows)
    except Exception:
        log.error("skill_store: get_all_skills failed", exc_info=True)
        return []


def get_enabled_skills() -> list[dict]:
    """Return only enabled skill rows."""
    return [s for s in get_all_skills() if s.get("enabled")]


# ---------------------------------------------------------------------------
#  Write
# ---------------------------------------------------------------------------

def upsert_skill(
    module_name: str,
    import_path: str = "",
    display_name: str = "",
    description: str = "",
    keywords: list[str] | None = None,
    always_on: bool = False,
    enabled: bool = True,
    sort_order: int = 100,
) -> bool:
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {_SCHEMA}.skill_registry
                    (module_name, import_path, display_name, description,
                     keywords, always_on, enabled, sort_order, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (module_name) DO UPDATE SET
                    import_path  = EXCLUDED.import_path,
                    display_name = EXCLUDED.display_name,
                    description  = EXCLUDED.description,
                    keywords     = EXCLUDED.keywords,
                    always_on    = EXCLUDED.always_on,
                    enabled      = EXCLUDED.enabled,
                    sort_order   = EXCLUDED.sort_order,
                    updated_at   = NOW()
            """, (
                module_name,
                import_path or f"mcp_server.skills.{module_name}",
                display_name,
                description,
                keywords or [],
                always_on,
                enabled,
                sort_order,
            ))
        conn.commit()
        conn.close()
        invalidate_cache()
        return True
    except Exception:
        log.error("skill_store: upsert failed for %s", module_name, exc_info=True)
        return False


def update_skill_enabled(module_name: str, enabled: bool) -> bool:
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE {_SCHEMA}.skill_registry
                SET enabled = %s, updated_at = NOW()
                WHERE module_name = %s
            """, (enabled, module_name))
        conn.commit()
        conn.close()
        invalidate_cache()
        return True
    except Exception:
        log.error("skill_store: update_enabled failed for %s", module_name, exc_info=True)
        return False


def update_skill_keywords(module_name: str, keywords: list[str]) -> bool:
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE {_SCHEMA}.skill_registry
                SET keywords = %s, updated_at = NOW()
                WHERE module_name = %s
            """, (keywords, module_name))
        conn.commit()
        conn.close()
        invalidate_cache()
        return True
    except Exception:
        log.error("skill_store: update_keywords failed for %s", module_name, exc_info=True)
        return False


def delete_skill(module_name: str) -> bool:
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {_SCHEMA}.skill_registry WHERE module_name = %s",
                (module_name,),
            )
        conn.commit()
        conn.close()
        invalidate_cache()
        return True
    except Exception:
        log.error("skill_store: delete failed for %s", module_name, exc_info=True)
        return False


# ---------------------------------------------------------------------------
#  Seed from hardcoded data (one-time migration)
# ---------------------------------------------------------------------------

def seed_from_hardcoded(
    keyword_routes: list[tuple[list[str], list]],
    skill_modules: list,
    always_modules: list,
) -> int:
    """Seed the registry table from the hardcoded tool_registry data.

    Only inserts rows that don't already exist (ON CONFLICT DO NOTHING).
    Returns number of rows inserted.
    """
    ensure_tables()

    # Build per-module keyword sets from the keyword_routes
    module_keywords: dict[str, set[str]] = {}
    for keywords_list, modules_list in keyword_routes:
        for mod in modules_list:
            name = mod.__name__.rsplit(".", 1)[-1]
            module_keywords.setdefault(name, set()).update(keywords_list)

    always_names = {m.__name__.rsplit(".", 1)[-1] for m in always_modules}

    inserted = 0
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            for mod in skill_modules:
                name = mod.__name__.rsplit(".", 1)[-1]
                import_path = mod.__name__
                display_name = name.replace("_", " ").title()
                description = (mod.__doc__ or "").strip().split("\n")[0][:200]
                keywords = sorted(module_keywords.get(name, set()))
                is_always = name in always_names

                cur.execute(f"""
                    INSERT INTO {_SCHEMA}.skill_registry
                        (module_name, import_path, display_name, description,
                         keywords, always_on, enabled, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
                    ON CONFLICT (module_name) DO NOTHING
                """, (
                    name, import_path, display_name, description,
                    keywords, is_always,
                    10 if is_always else 100,
                ))
                if cur.rowcount > 0:
                    inserted += 1
        conn.commit()
        conn.close()
        if inserted:
            invalidate_cache()
            log.info("skill_store: seeded %d skills from hardcoded config", inserted)
    except Exception:
        log.error("skill_store: seed failed", exc_info=True)

    return inserted
