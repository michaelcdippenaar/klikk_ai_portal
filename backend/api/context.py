"""
Context Management API — view, add, delete RAG context.
Provides a dashboard for managing global facts, element context,
and scraping chat sessions for context extraction.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Chat session log directory
_CHAT_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "chat_sessions"


# --- Models ---

class FactCreate(BaseModel):
    content: str

class ContextNoteCreate(BaseModel):
    dimension_name: str
    element_name: str
    context_note: str


# --- Global Facts ---

@router.get("/facts")
async def list_facts(limit: int = 100):
    """List all global facts (newest first)."""
    from context_store import is_available, list_global_context, ensure_tables
    if not is_available():
        return {"facts": [], "error": "Context store not available"}
    ensure_tables()
    facts = list_global_context(limit=limit)
    return {"facts": facts, "count": len(facts)}


@router.post("/facts")
async def add_fact(body: FactCreate):
    """Add a manual global fact."""
    from context_store import is_available, ensure_tables, save_global_context
    if not is_available():
        raise HTTPException(500, "Context store not available")
    ensure_tables()
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "Content is required")
    row_id = save_global_context(content, metadata={"source": "manual"})
    return {"id": row_id, "status": "saved"}


@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: int):
    """Delete a global fact by ID."""
    from context_store import is_available, _get_conn
    from config import settings
    if not is_available():
        raise HTTPException(500, "Context store not available")
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {settings.rag_schema}.global_context WHERE id = %s RETURNING id", (fact_id,))
        deleted = cur.fetchone()
    conn.commit()
    conn.close()
    if not deleted:
        raise HTTPException(404, "Fact not found")
    return {"status": "deleted", "id": fact_id}


# --- Element Context ---

@router.get("/elements")
async def list_element_contexts(limit: int = 100):
    """List element context notes from RAG store."""
    import psycopg2
    import psycopg2.extras
    from config import settings
    try:
        conn = psycopg2.connect(
            host=settings.pg_bi_host, port=settings.pg_bi_port,
            dbname=settings.pg_bi_db, user=settings.pg_bi_user,
            password=settings.pg_bi_password,
        )
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"""
                SELECT doc_id, title, content, metadata, indexed_at
                FROM {settings.rag_schema}.documents
                WHERE doc_type = 'element_context'
                ORDER BY indexed_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
        conn.close()
        return {
            "notes": [
                {
                    "doc_id": r["doc_id"],
                    "title": r["title"],
                    "content": r["content"],
                    "metadata": r["metadata"],
                    "indexed_at": str(r["indexed_at"]),
                }
                for r in rows
            ],
            "count": len(rows),
        }
    except Exception as e:
        return {"notes": [], "count": 0, "error": str(e)}


@router.post("/elements")
async def add_element_context(body: ContextNoteCreate):
    """Manually add a context note for a dimension element."""
    from mcp_server.skills.element_context import save_element_context
    result = save_element_context(
        dimension_name=body.dimension_name,
        element_name=body.element_name,
        context_note=body.context_note,
    )
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


@router.delete("/elements/{doc_id:path}")
async def delete_element_context(doc_id: str):
    """Delete an element context note by doc_id."""
    import psycopg2
    from config import settings
    try:
        conn = psycopg2.connect(
            host=settings.pg_bi_host, port=settings.pg_bi_port,
            dbname=settings.pg_bi_db, user=settings.pg_bi_user,
            password=settings.pg_bi_password,
        )
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {settings.rag_schema}.documents WHERE doc_id = %s RETURNING doc_id", (doc_id,))
            deleted = cur.fetchone()
        conn.commit()
        conn.close()
        if not deleted:
            raise HTTPException(404, "Context note not found")
        return {"status": "deleted", "doc_id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# --- RAG Stats ---

@router.get("/stats")
async def rag_stats():
    """RAG index statistics — document counts by type."""
    import psycopg2
    import psycopg2.extras
    from config import settings
    try:
        conn = psycopg2.connect(
            host=settings.pg_bi_host, port=settings.pg_bi_port,
            dbname=settings.pg_bi_db, user=settings.pg_bi_user,
            password=settings.pg_bi_password,
        )
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Doc counts by type
            cur.execute(f"""
                SELECT doc_type, COUNT(*) as count,
                       MIN(indexed_at) as oldest,
                       MAX(indexed_at) as newest
                FROM {settings.rag_schema}.documents
                GROUP BY doc_type
                ORDER BY count DESC
            """)
            doc_stats = [
                {"doc_type": r["doc_type"], "count": r["count"],
                 "oldest": str(r["oldest"]), "newest": str(r["newest"])}
                for r in cur.fetchall()
            ]

            # Global context count
            cur.execute(f"SELECT COUNT(*) FROM {settings.rag_schema}.global_context")
            global_count = cur.fetchone()[0]

            # Conversation context count
            cur.execute(f"SELECT COUNT(*) FROM {settings.rag_schema}.conversation_context")
            conv_count = cur.fetchone()[0]

            # Distinct sessions
            cur.execute(f"SELECT COUNT(DISTINCT session_id) FROM {settings.rag_schema}.conversation_context")
            session_count = cur.fetchone()[0]

        conn.close()

        total_docs = sum(s["count"] for s in doc_stats)
        return {
            "documents": {"total": total_docs, "by_type": doc_stats},
            "global_facts": global_count,
            "conversation_turns": conv_count,
            "chat_sessions_indexed": session_count,
        }
    except Exception as e:
        return {"error": str(e)}


# --- Chat Scraping ---

@router.get("/sessions")
async def list_chat_sessions():
    """List available chat sessions that can be scraped for context."""
    if not _CHAT_LOG_DIR.exists():
        return {"sessions": [], "count": 0}
    sessions = []
    for path in sorted(_CHAT_LOG_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = data.get("messages", [])
            user_msgs = [m for m in messages if m.get("role") == "user"]
            preview = user_msgs[0]["content"][:100] if user_msgs else ""
            sessions.append({
                "id": path.stem,
                "file": path.name,
                "message_count": len(messages),
                "preview": preview,
                "modified": str(Path(path).stat().st_mtime),
            })
        except Exception:
            continue
    return {"sessions": sessions, "count": len(sessions)}


class ScrapeRequest(BaseModel):
    session_ids: list[str] | None = None  # None = all sessions


@router.post("/scrape")
async def scrape_sessions(body: ScrapeRequest):
    """
    Scrape chat sessions for business context using LLM extraction.
    Reads chat history files, sends conversation to LLM to extract facts,
    then saves them as global context.
    """
    from context_store import is_available, ensure_tables, save_global_context
    if not is_available():
        raise HTTPException(500, "Context store not available")
    ensure_tables()

    if not _CHAT_LOG_DIR.exists():
        return {"facts_extracted": 0, "sessions_processed": 0, "error": "No chat sessions found"}

    # Collect sessions to process
    if body.session_ids:
        session_files = [_CHAT_LOG_DIR / f"{sid}.json" for sid in body.session_ids]
        session_files = [f for f in session_files if f.exists()]
    else:
        session_files = sorted(_CHAT_LOG_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]

    if not session_files:
        return {"facts_extracted": 0, "sessions_processed": 0}

    from config import settings

    _SCRAPE_PROMPT = """You extract business facts, definitions, and context from chat conversations.

Look for things the user EXPLAINS, TEACHES, or CORRECTS — definitions, relationships, business context,
data meanings, process descriptions, entity explanations.

Return a JSON array of concise fact strings. Each fact should:
- Stand alone and be useful in future conversations
- Be a genuine business fact, not a question or command
- Include specific details (names, codes, relationships)

If there are no facts to extract, return an empty array: []

Examples of GOOD facts:
- "Tracking_1 dimension represents business segments: Property, Event Equipment, Financial Investments"
- "Investec portfolio exports show point-in-time holdings snapshots with cost basis and P&L"
- "Klikk (Pty) Ltd entity GUID is 41ebfa0e-012e-4ff1-82ba-a9a7585c536c"
- "Balance sheet accounts accumulate YTD, P&L accounts show period amounts"

Do NOT extract:
- Questions the user asked
- Error messages or status updates
- Tool call details or technical responses"""

    total_facts = 0
    sessions_processed = 0
    details = []

    for session_file in session_files:
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = data.get("messages", [])
            if len(messages) < 2:
                continue

            # Build conversation summary for LLM
            conversation = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content:
                    conversation.append(f"{role.upper()}: {content}")

            conv_text = "\n\n".join(conversation)
            if len(conv_text) > 8000:
                conv_text = conv_text[:8000] + "\n... (truncated)"

            # Call LLM to extract facts
            provider = settings.ai_provider.lower()
            raw = "[]"

            if provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                resp = client.messages.create(
                    model=settings.anthropic_model,
                    system="You extract business facts from conversations. Return ONLY a valid JSON array of strings.",
                    messages=[{"role": "user", "content": f"{_SCRAPE_PROMPT}\n\n---\n\n{conv_text}\n\n---\nReturn JSON array:"}],
                    max_tokens=2000,
                )
                raw = resp.content[0].text.strip()
            elif provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You extract business facts from conversations. Return ONLY a valid JSON array of strings."},
                        {"role": "user", "content": f"{_SCRAPE_PROMPT}\n\n---\n\n{conv_text}\n\n---\nReturn JSON array:"},
                    ],
                    max_tokens=2000,
                )
                raw = resp.choices[0].message.content or "[]"

            # Parse JSON
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if len(lines) > 2 else "[]"
                raw = raw.strip()

            facts = json.loads(raw)
            if not isinstance(facts, list):
                facts = []

            session_facts = 0
            for fact in facts:
                if isinstance(fact, str) and fact.strip():
                    save_global_context(fact.strip(), metadata={"source": "chat_scrape", "session_id": session_file.stem})
                    session_facts += 1

            total_facts += session_facts
            sessions_processed += 1
            details.append({"session_id": session_file.stem, "facts_extracted": session_facts})

        except Exception as e:
            details.append({"session_id": session_file.stem, "error": str(e)})

    return {
        "facts_extracted": total_facts,
        "sessions_processed": sessions_processed,
        "details": details,
    }


# --- Search ---

@router.get("/search")
async def search_context(q: str, top_k: int = 10):
    """Semantic search across all context (global facts + RAG documents)."""
    results = {}

    # Search global facts
    try:
        from context_store import is_available, search_global_context
        if is_available():
            results["global_facts"] = search_global_context(q, top_k=top_k)
    except Exception as e:
        results["global_facts_error"] = str(e)

    # Search RAG documents
    try:
        from rag.retriever import retrieve_with_scores
        # This function may not exist, fall back to raw query
        raise ImportError("use raw")
    except ImportError:
        try:
            import psycopg2
            import psycopg2.extras
            import numpy as np
            from config import settings
            from context_store import _embed_query

            qvec = _embed_query(q)
            conn = psycopg2.connect(
                host=settings.pg_bi_host, port=settings.pg_bi_port,
                dbname=settings.pg_bi_db, user=settings.pg_bi_user,
                password=settings.pg_bi_password,
            )
            from pgvector.psycopg2 import register_vector
            register_vector(conn)
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(f"""
                    SELECT doc_id, doc_type, title, content, metadata,
                           1 - (embedding <=> %s) AS score
                    FROM {settings.rag_schema}.documents
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, (np.array(qvec), np.array(qvec), top_k))
                rows = cur.fetchall()
            conn.close()
            results["documents"] = [
                {
                    "doc_id": r["doc_id"],
                    "doc_type": r["doc_type"],
                    "title": r["title"],
                    "content": r["content"][:500],
                    "score": round(float(r["score"]), 4),
                }
                for r in rows
            ]
        except Exception as e:
            results["documents_error"] = str(e)

    return results
