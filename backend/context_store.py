"""
Context Store — pgvector-backed Global and Conversation context.

Two layers:
1. **Global Context**: Facts that persist across all sessions. When the user
   explains "Absa is a South African bank listed on JSE", this is saved as
   a globally-retrievable fact.
2. **Conversation Context**: Per-session context — what was discussed, PAW
   variables (cube, server, queryState, viewName) active during the turn.

Both are embedded via VoyageAI and stored in pgvector for semantic search.

Tables live in the configured rag_schema (default: agent_rag):
  - agent_rag.global_context (id, content, embedding, metadata, created_at)
  - agent_rag.conversation_context (id, session_id, role, content, embedding, metadata, created_at)
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import numpy as np
import psycopg2
import psycopg2.extras
import psycopg2.pool

from config import settings
from logger import log

try:
    import voyageai
    from pgvector.psycopg2 import register_vector
    _AVAILABLE = bool(settings.voyage_api_key)
except ImportError:
    _AVAILABLE = False


def is_available() -> bool:
    return _AVAILABLE


# ---------------------------------------------------------------------------
#  Connection pooling
# ---------------------------------------------------------------------------
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        with _pool_lock:
            if _pool is None or _pool.closed:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2, maxconn=10,
                    host=settings.pg_bi_host, port=settings.pg_bi_port,
                    dbname=settings.pg_bi_db, user=settings.pg_bi_user,
                    password=settings.pg_bi_password,
                )
    return _pool


def _get_conn():
    conn = _get_pool().getconn()
    register_vector(conn)
    return conn


def _put_conn(conn):
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Embedding cache (LRU by content hash, max 500 entries)
# ---------------------------------------------------------------------------
_embed_cache: OrderedDict[str, list[float]] = OrderedDict()
_EMBED_CACHE_MAX = 500
_embed_cache_lock = threading.Lock()
_voyage_client: voyageai.Client | None = None


def _get_voyage_client() -> voyageai.Client:
    global _voyage_client
    if _voyage_client is None:
        _voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
    return _voyage_client


def _cache_key(text: str, input_type: str) -> str:
    return hashlib.md5(f"{input_type}:{text}".encode()).hexdigest()


def _embed(texts: list[str]) -> list[list[float]]:
    import time as _t
    t0 = _t.monotonic()
    client = _get_voyage_client()
    results: list[list[float]] = []
    uncached_texts: list[str] = []
    uncached_indices: list[int] = []

    # Check cache first
    with _embed_cache_lock:
        for i, text in enumerate(texts):
            key = _cache_key(text, "document")
            if key in _embed_cache:
                _embed_cache.move_to_end(key)
                results.append(_embed_cache[key])
            else:
                results.append([])  # placeholder
                uncached_texts.append(text)
                uncached_indices.append(i)

    # Fetch uncached embeddings
    if uncached_texts:
        fetched: list[list[float]] = []
        for i in range(0, len(uncached_texts), 128):
            batch = uncached_texts[i:i + 128]
            resp = client.embed(batch, model=settings.voyage_model, input_type="document")
            fetched.extend(resp.embeddings)
        with _embed_cache_lock:
            for idx, emb in zip(uncached_indices, fetched):
                results[idx] = emb
                key = _cache_key(texts[idx], "document")
                _embed_cache[key] = emb
                if len(_embed_cache) > _EMBED_CACHE_MAX:
                    _embed_cache.popitem(last=False)

    dur = int((_t.monotonic() - t0) * 1000)
    cache_hits = len(texts) - len(uncached_texts)
    log.info("VoyageAI embed: %d texts in %dms (cache hits: %d)", len(texts), dur, cache_hits,
             extra={"count": len(texts), "duration_ms": dur, "cache_hits": cache_hits})
    return results


def _embed_query(text: str) -> list[float]:
    import time as _t
    t0 = _t.monotonic()
    key = _cache_key(text, "query")
    with _embed_cache_lock:
        if key in _embed_cache:
            _embed_cache.move_to_end(key)
            dur = int((_t.monotonic() - t0) * 1000)
            log.info("VoyageAI embed query: %dms (cached)", dur, extra={"duration_ms": dur})
            return _embed_cache[key]

    client = _get_voyage_client()
    resp = client.embed([text], model=settings.voyage_model, input_type="query")
    emb = resp.embeddings[0]
    with _embed_cache_lock:
        _embed_cache[key] = emb
        if len(_embed_cache) > _EMBED_CACHE_MAX:
            _embed_cache.popitem(last=False)
    dur = int((_t.monotonic() - t0) * 1000)
    log.info("VoyageAI embed query: %dms", dur, extra={"duration_ms": dur})
    return emb


_SCHEMA = settings.rag_schema


def ensure_tables() -> None:
    """Create global_context and conversation_context tables if missing."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_SCHEMA}.global_context (
                id          BIGSERIAL PRIMARY KEY,
                content     TEXT NOT NULL,
                embedding   vector({settings.embedding_dim}),
                metadata    JSONB DEFAULT '{{}}',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_SCHEMA}.conversation_context (
                id          BIGSERIAL PRIMARY KEY,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT 'user',
                content     TEXT NOT NULL,
                embedding   vector({settings.embedding_dim}),
                metadata    JSONB DEFAULT '{{}}',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_conv_ctx_session
            ON {_SCHEMA}.conversation_context (session_id)
        """)
    conn.commit()
    _put_conn(conn)


# ---------------------------------------------------------------------------
#  Global Context
# ---------------------------------------------------------------------------

def save_global_context(content: str, metadata: dict | None = None) -> int:
    """Save a fact/explanation to global context. Returns the row id."""
    emb = _embed([content])[0]
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {_SCHEMA}.global_context (content, embedding, metadata)
                VALUES (%s, %s, %s) RETURNING id""",
            (content, np.array(emb), json.dumps(metadata or {})),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    _put_conn(conn)
    return row_id


def search_global_context(query: str, top_k: int = 5, min_score: float = 0.0) -> list[dict]:
    """Semantic search over global context. Returns list of {id, content, metadata, score}."""
    qvec = _embed_query(query)
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            f"""SELECT id, content, metadata, created_at,
                       1 - (embedding <=> %s) AS score
                FROM {_SCHEMA}.global_context
                ORDER BY embedding <=> %s
                LIMIT %s""",
            (np.array(qvec), np.array(qvec), top_k),
        )
        rows = cur.fetchall()
    _put_conn(conn)
    results = []
    for r in rows:
        score = float(r["score"])
        if score < min_score:
            continue
        results.append({
            "id": r["id"],
            "content": r["content"],
            "metadata": r["metadata"],
            "created_at": str(r["created_at"]),
            "score": round(score, 4),
        })
    return results


def list_global_context(limit: int = 50) -> list[dict]:
    """List recent global context entries (no embedding search, just newest)."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            f"SELECT id, content, metadata, created_at FROM {_SCHEMA}.global_context ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    _put_conn(conn)
    return [{"id": r["id"], "content": r["content"], "metadata": r["metadata"], "created_at": str(r["created_at"])} for r in rows]


# ---------------------------------------------------------------------------
#  Conversation Context
# ---------------------------------------------------------------------------

def save_conversation_turn(
    session_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> int:
    """Save a single conversation turn (user or assistant message) with embedding. Returns row id."""
    if not content or not content.strip():
        return -1
    emb = _embed([content])[0]
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {_SCHEMA}.conversation_context
                    (session_id, role, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (session_id, role, content, np.array(emb), json.dumps(metadata or {})),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    _put_conn(conn)
    return row_id


def search_conversation_context(
    query: str,
    session_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.0,
) -> list[dict]:
    """Semantic search over conversation context. Filter by session_id or search all sessions."""
    qvec = _embed_query(query)
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if session_id:
            cur.execute(
                f"""SELECT id, session_id, role, content, metadata, created_at,
                           1 - (embedding <=> %s) AS score
                    FROM {_SCHEMA}.conversation_context
                    WHERE session_id = %s
                    ORDER BY embedding <=> %s
                    LIMIT %s""",
                (np.array(qvec), session_id, np.array(qvec), top_k),
            )
        else:
            cur.execute(
                f"""SELECT id, session_id, role, content, metadata, created_at,
                           1 - (embedding <=> %s) AS score
                    FROM {_SCHEMA}.conversation_context
                    ORDER BY embedding <=> %s
                    LIMIT %s""",
                (np.array(qvec), np.array(qvec), top_k),
            )
        rows = cur.fetchall()
    _put_conn(conn)
    results = []
    for r in rows:
        score = float(r["score"])
        if score < min_score:
            continue
        results.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "role": r["role"],
            "content": r["content"],
            "metadata": r["metadata"],
            "created_at": str(r["created_at"]),
            "score": round(score, 4),
        })
    return results
