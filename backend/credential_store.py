"""
Credential Store — DB-backed credential/config storage.

Stores API keys and other secrets in agent_rag.credentials table.
Provides get_credential() which checks DB first, falls back to .env.
Values are cached in-memory with a short TTL to avoid hitting DB on every API call.

Table: agent_rag.credentials
  - key       TEXT PRIMARY KEY   (e.g. "anthropic_api_key", "voyage_api_key")
  - value     TEXT               (the secret value)
  - label     TEXT               (human-readable label, e.g. "Anthropic API Key")
  - updated_at TIMESTAMPTZ
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import psycopg2
import psycopg2.extras

from config import settings
from logger import log

# ---------------------------------------------------------------------------
#  Connection (reuses same PG BI database as context_store / widget_store)
# ---------------------------------------------------------------------------

def _get_conn():
    return psycopg2.connect(
        host=settings.pg_bi_host,
        port=settings.pg_bi_port,
        dbname=settings.pg_bi_db,
        user=settings.pg_bi_user,
        password=settings.pg_bi_password,
    )


_SCHEMA = settings.rag_schema  # default: "agent_rag"

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
                CREATE TABLE IF NOT EXISTS {_SCHEMA}.credentials (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL DEFAULT '',
                    label       TEXT NOT NULL DEFAULT '',
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
        conn.close()
        _tables_ok = True
    except Exception:
        log.warning("credential_store: table creation failed", exc_info=True)


# ---------------------------------------------------------------------------
#  In-memory cache (key → (value, fetched_at))
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[str, float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 60  # seconds — re-read from DB every 60s


def _cache_get(key: str) -> Optional[str]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.monotonic() - entry[1]) < _CACHE_TTL:
            return entry[0]
    return None


def _cache_set(key: str, value: str):
    with _cache_lock:
        _cache[key] = (value, time.monotonic())


def _cache_invalidate(key: str):
    with _cache_lock:
        _cache.pop(key, None)


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def get_credential(key: str, fallback: str = "") -> str:
    """Get a credential value. Checks DB first (with cache), falls back to .env value.

    Args:
        key: credential key, e.g. "anthropic_api_key"
        fallback: value to return if not found anywhere (typically settings.X)
    """
    # Check cache first
    cached = _cache_get(key)
    if cached is not None:
        return cached

    # Try DB
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT value FROM {_SCHEMA}.credentials WHERE key = %s",
                (key,),
            )
            row = cur.fetchone()
        conn.close()
        if row and row[0]:
            _cache_set(key, row[0])
            return row[0]
    except Exception:
        log.debug("credential_store: DB read failed for %s, using fallback", key)

    # Fall back to .env value
    _cache_set(key, fallback)
    return fallback


def set_credential(key: str, value: str, label: str = "") -> bool:
    """Upsert a credential in the DB."""
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {_SCHEMA}.credentials (key, value, label, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value,
                        label = COALESCE(NULLIF(EXCLUDED.label, ''), {_SCHEMA}.credentials.label),
                        updated_at = NOW()
            """, (key, value, label))
        conn.commit()
        conn.close()
        _cache_invalidate(key)
        log.info("credential_store: set %s", key)
        return True
    except Exception:
        log.error("credential_store: failed to set %s", key, exc_info=True)
        return False


def delete_credential(key: str) -> bool:
    """Delete a credential from the DB."""
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {_SCHEMA}.credentials WHERE key = %s", (key,))
        conn.commit()
        conn.close()
        _cache_invalidate(key)
        return True
    except Exception:
        log.error("credential_store: failed to delete %s", key, exc_info=True)
        return False


def list_credentials() -> list[dict]:
    """List all credentials (values are masked for safety)."""
    try:
        ensure_tables()
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT key, label, value, updated_at
                FROM {_SCHEMA}.credentials
                ORDER BY key
            """)
            rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            val = row["value"] or ""
            masked = val[:8] + "..." + val[-4:] if len(val) > 16 else "***"
            result.append({
                "key": row["key"],
                "label": row["label"] or row["key"],
                "hint": masked,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "has_value": bool(val),
            })
        return result
    except Exception:
        log.error("credential_store: list failed", exc_info=True)
        return []


# ---------------------------------------------------------------------------
#  Known credential definitions (for the setup UI)
# ---------------------------------------------------------------------------
KNOWN_CREDENTIALS = [
    {"key": "anthropic_api_key", "label": "Anthropic API Key", "group": "AI Provider"},
    {"key": "openai_api_key", "label": "OpenAI API Key", "group": "AI Provider"},
    {"key": "voyage_api_key", "label": "VoyageAI API Key", "group": "Embeddings"},
    {"key": "web_search_api_key", "label": "Web Search API Key", "group": "Web Search"},
    {"key": "financials_api_token", "label": "Klikk Financials API Token", "group": "Integrations"},
]
