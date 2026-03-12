"""
RAG retriever — queries pgvector for semantically similar chunks.
Used by system_prompt.py to inject context before every Claude call.
"""
from __future__ import annotations

import sys
import os

import numpy as np
import psycopg2
import psycopg2.extras

# Allow running from agent/ directory
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


def _get_query_embedding(query: str) -> list[float] | None:
    if not _VOYAGE_AVAILABLE:
        return None
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = client.embed([query], model=settings.voyage_model, input_type="query")
    return result.embeddings[0]


def retrieve(query: str) -> str:
    """
    Embed query, search pgvector, return top-k chunks as a formatted context string.
    Returns empty string if RAG is unavailable or no results found.
    """
    if not _PGVECTOR_AVAILABLE or not _VOYAGE_AVAILABLE:
        return ""

    embedding = _get_query_embedding(query)
    if not embedding:
        return ""

    try:
        conn = psycopg2.connect(
            host=settings.pg_bi_host,
            port=settings.pg_bi_port,
            dbname=settings.pg_bi_db,
            user=settings.pg_bi_user,
            password=settings.pg_bi_password,
        )
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
        conn.close()
    except Exception:
        return ""

    if not rows:
        return ""

    parts = []
    for row in rows:
        parts.append(
            f"[{row['doc_type']} | {row['source_path']} | score={row['score']:.2f}]\n"
            f"## {row['title']}\n{row['content']}"
        )
    return "\n\n---\n\n".join(parts)
