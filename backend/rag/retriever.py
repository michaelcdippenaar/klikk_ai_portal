"""
RAG retriever — queries pgvector for semantically similar chunks.
Used by system_prompt.py to inject context before every agent call.

Optimisations:
- VoyageAI client is a singleton (created once).
- Postgres uses a SimpleConnectionPool (reuses connections).
"""
from __future__ import annotations

import sys
import os
import threading

import numpy as np
import psycopg2
import psycopg2.extras
import psycopg2.pool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import settings

try:
    from pgvector.psycopg2 import register_vector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    _PGVECTOR_AVAILABLE = False

try:
    import voyageai
    _VOYAGE_AVAILABLE = bool(settings.voyage_api_key)
except ImportError:
    _VOYAGE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_voyage_client = None
_voyage_lock = threading.Lock()

def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        with _voyage_lock:
            if _voyage_client is None:
                _voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
    return _voyage_client


_pg_pool = None
_pg_lock = threading.Lock()

def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        with _pg_lock:
            if _pg_pool is None:
                _pg_pool = psycopg2.pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=5,
                    host=settings.pg_bi_host,
                    port=settings.pg_bi_port,
                    dbname=settings.pg_bi_db,
                    user=settings.pg_bi_user,
                    password=settings.pg_bi_password,
                )
    return _pg_pool


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _get_query_embedding(query: str) -> list[float] | None:
    if not _VOYAGE_AVAILABLE:
        return None
    client = _get_voyage_client()
    result = client.embed([query], model=settings.voyage_model, input_type="query")
    return result.embeddings[0]


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str) -> str:
    """
    Embed query, search pgvector, return top-k chunks as formatted context.
    Returns empty string if RAG is unavailable or no results found.
    """
    if not _PGVECTOR_AVAILABLE or not _VOYAGE_AVAILABLE:
        return ""

    embedding = _get_query_embedding(query)
    if not embedding:
        return ""

    pool = _get_pg_pool()
    conn = None
    try:
        conn = pool.getconn()
        register_vector(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""
                SELECT title, content, doc_type, source_path,
                       1 - (embedding <=> %s) AS score
                FROM {settings.rag_schema}.documents
                WHERE 1 - (embedding <=> %s) >= %s
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (
                    np.array(embedding),
                    np.array(embedding),
                    settings.rag_min_score,
                    np.array(embedding),
                    settings.rag_top_k,
                ),
            )
            rows = cur.fetchall()
    except Exception:
        return ""
    finally:
        if conn is not None:
            try:
                pool.putconn(conn)
            except Exception:
                pass

    if not rows:
        return ""

    parts = []
    for row in rows:
        parts.append(
            f"[{row['doc_type']} | {row['source_path']} | score={row['score']:.2f}]\n"
            f"## {row['title']}\n{row['content']}"
        )
    return "\n\n---\n\n".join(parts)
