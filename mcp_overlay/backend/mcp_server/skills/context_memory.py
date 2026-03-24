"""
Skill: Context Memory — Global Context and Conversation Context backed by pgvector.

Global Context: Persistent facts across all sessions.
  "Absa is a South African bank listed on JSE as ABG" → saved once, retrievable everywhere.

Conversation Context: Every chat turn is embedded. Search past conversations by meaning.

Requires VOYAGE_API_KEY and pgvector in klikk_bi_etl (agent_rag schema).
"""
from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import settings
from logger import log


def _ensure():
    from context_store import ensure_tables, is_available
    if not is_available():
        return False
    ensure_tables()
    return True


def save_global_fact(content: str, tags: str = "") -> dict[str, Any]:
    """
    Save a fact or explanation to Global Context (persists across all sessions).
    Use when the user explains something or you learn a useful fact.
    Examples: "Absa is a South African bank", "acc_001 is office rent ~R45K/month".

    content: The fact or explanation to remember.
    tags: Optional comma-separated tags for metadata (e.g. "share,JSE,banking").
    """
    if not _ensure():
        return {"error": "Context store not available (VOYAGE_API_KEY not set or pgvector not installed)."}
    try:
        from context_store import save_global_context
        meta = {}
        if tags:
            meta["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        row_id = save_global_context(content, metadata=meta)
        return {"status": "saved", "id": row_id, "content_preview": content[:200]}
    except Exception as e:
        log.error("save_global_fact error: %s", e, extra={"tool": "context_memory"})
        return {"error": str(e)}


def search_global_facts(query: str, top_k: int = 5) -> dict[str, Any]:
    """
    Semantic search over Global Context — finds facts saved across all sessions.
    Use to recall what the user has explained before or facts you stored.

    query: Natural language query, e.g. "What is Absa?" or "office rent account".
    top_k: Max results (default 5).
    """
    if not _ensure():
        return {"error": "Context store not available."}
    try:
        from context_store import search_global_context
        results = search_global_context(query, top_k=min(int(top_k), 20), min_score=settings.rag_min_score)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        log.error("search_global_facts error: %s", e, extra={"tool": "context_memory"})
        return {"error": str(e)}


def list_global_facts(limit: int = 20) -> dict[str, Any]:
    """
    List recent Global Context entries (most recent first, no search).
    """
    if not _ensure():
        return {"error": "Context store not available."}
    try:
        from context_store import list_global_context
        entries = list_global_context(limit=min(int(limit), 100))
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        log.error("list_global_facts error: %s", e, extra={"tool": "context_memory"})
        return {"error": str(e)}


def search_past_conversations(query: str, session_id: str = "", top_k: int = 5) -> dict[str, Any]:
    """
    Semantic search over past conversation turns (all sessions or one specific session).
    Finds what was discussed before, even in other chat sessions.

    query: Natural language query, e.g. "Absa dividend" or "cashflow mapping".
    session_id: Optional. Restrict to a specific session, or leave empty for all sessions.
    top_k: Max results (default 5).
    """
    if not _ensure():
        return {"error": "Context store not available."}
    try:
        from context_store import search_conversation_context
        results = search_conversation_context(
            query, session_id=session_id or None,
            top_k=min(int(top_k), 20), min_score=settings.rag_min_score,
        )
        return {"query": query, "session_id": session_id or "all", "results": results, "count": len(results)}
    except Exception as e:
        log.error("search_past_conversations error: %s", e, extra={"tool": "context_memory"})
        return {"error": str(e)}


# ---------------------------------------------------------------------------
#  Tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "save_global_fact",
        "description": (
            "Save a fact or explanation to Global Context (persists across all sessions). "
            "Use when the user explains something or you learn a useful fact — "
            "e.g. 'Absa is a South African bank listed on JSE as ABG'. "
            "Stored in pgvector for semantic search. Requires VOYAGE_API_KEY."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The fact or explanation to remember."},
                "tags": {"type": "string", "description": "Optional comma-separated tags, e.g. 'share,JSE,banking'."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "search_global_facts",
        "description": (
            "Semantic search over Global Context — finds facts saved across all sessions. "
            "Use to recall what the user has explained or facts previously stored. "
            "e.g. 'What is Absa?', 'office rent account'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query."},
                "top_k": {"type": "integer", "description": "Max results (default 5)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_global_facts",
        "description": "List recent Global Context entries (most recent first).",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max entries (default 20)."},
            },
        },
    },
    {
        "name": "search_past_conversations",
        "description": (
            "Semantic search over past conversation turns from all chat sessions or one session. "
            "Finds what was discussed before — e.g. 'Absa dividend', 'cashflow mapping'. "
            "Each turn is stored with PAW variables (cube, server, view) as metadata."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query."},
                "session_id": {"type": "string", "description": "Optional. Restrict to a specific session."},
                "top_k": {"type": "integer", "description": "Max results (default 5)."},
            },
            "required": ["query"],
        },
    },
]

TOOL_FUNCTIONS = {
    "save_global_fact": save_global_fact,
    "search_global_facts": search_global_facts,
    "list_global_facts": list_global_facts,
    "search_past_conversations": search_past_conversations,
}
