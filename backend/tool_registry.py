"""
Tool registry — single source of truth for all tool schemas and functions.
Supports both Anthropic and OpenAI tool-calling formats.

Optimisation: route_tools_for_message() returns only the subset of tool
schemas relevant to a given user message, reducing token count and
improving tool selection accuracy.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from logger import log

from mcp_server.skills import (
    mcp_bridge,
    tm1_rest_api,
    pattern_analysis,
    kpi_monitor,
    validation,
    element_context,
    web_search,
    google_drive,
    widget_generation,
    paw_integration,
    session_review,
    financials_data,
    statistics,
    share_metrics,
    context_memory,
    report_builder,
    ai_setup,
)

_SKILL_MODULES = [
    mcp_bridge,
    tm1_rest_api,
    pattern_analysis,
    kpi_monitor,
    validation,
    element_context,
    web_search,
    google_drive,
    widget_generation,
    paw_integration,
    session_review,
    financials_data,
    statistics,
    share_metrics,
    context_memory,
    report_builder,
    ai_setup,
]

# ---------------------------------------------------------------------------
# Full registries (used for call_tool dispatch — always complete)
# ---------------------------------------------------------------------------

ANTHROPIC_SCHEMAS: list[dict] = []
for _mod in _SKILL_MODULES:
    ANTHROPIC_SCHEMAS.extend(_mod.TOOL_SCHEMAS)

_FUNCTIONS: dict[str, Any] = {}
for _mod in _SKILL_MODULES:
    _FUNCTIONS.update(_mod.TOOL_FUNCTIONS)


def _to_openai_schema(anthropic_schema: dict) -> dict:
    """Convert one Anthropic tool schema to OpenAI function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": anthropic_schema["name"],
            "description": anthropic_schema.get("description", ""),
            "parameters": anthropic_schema.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


OPENAI_SCHEMAS: list[dict] = [_to_openai_schema(s) for s in ANTHROPIC_SCHEMAS]

# ---------------------------------------------------------------------------
# Tool routing — keyword-based module selection
# ---------------------------------------------------------------------------

_ALWAYS_MODULES = [mcp_bridge, widget_generation]

_KEYWORD_ROUTES: list[tuple[list[str], list]] = [
    (
        ["server status", "message log", "transaction log", "thread", "session",
         "sandbox", "error log", "rest api", "server health", "server version",
         "who is logged", "active user", "write value", "write cell",
         "execute view", "named view", "run view", "rpt_", "report view"],
        [tm1_rest_api],
    ),
    (
        ["process", "chore", "ti ", "turbointegrator", "run process",
         "execute process", "schedule"],
        [mcp_bridge],
    ),
    (
        ["postgres", "sql", "xero", "gl data", "general ledger", "database",
         "pg ", "trial_balance import", "share", "stock", "portfolio",
         "investment", "dividend", "price history", "holdings", "investec",
         "symbol", "pricepoint"],
        [mcp_bridge],
    ),
    (
        ["vectorized", "vector search", "financials data", "data guide",
         "how data fits", "corpora", "rag financials", "klikk financials",
         "trail balance", "xero cube", "consolidate journals"],
        [financials_data],
    ),
    (
        ["anomal", "pattern", "outlier", "variance", "spike", "unusual"],
        [pattern_analysis],
    ),
    (
        ["kpi", "metric", "threshold", "alert", "monitor", "target"],
        [kpi_monitor],
    ),
    (
        ["validate", "verification", "check model", "verify", "reconcil"],
        [validation],
    ),
    (
        ["element context", "save context", "what do we know about",
         "index dimension", "index element", "remember"],
        [element_context],
    ),
    (
        ["search", "google", "look up", "internet", "stock price",
         "current price", "news", "web"],
        [web_search],
    ),
    (
        ["drive", "google drive", "document", "gdrive"],
        [google_drive],
    ),
    (
        ["paw", "planning analytics workspace", "embed", "paw book",
         "paw view", "writeback", "view mdx", "query state", "get view data",
         "current view", "view query state", "extract values", "view data"],
        [paw_integration],
    ),
    (
        ["session", "chat log", "review session", "review chat",
         "improve skill", "improve tool", "chat history log"],
        [session_review],
    ),
    (
        ["forecast", "trend", "pattern", "time series", "history predict",
         "statistics", "linear trend", "growth rate", "volatility"],
        [statistics],
    ),
    (
        ["dividend per share", "payout ratio", "eps", "dividend yield",
         "share metrics", "dps", "retention ratio", "dividends per share"],
        [share_metrics],
    ),
    (
        ["remember", "global context", "save fact", "what did i say",
         "past conversation", "what do we know", "recall", "explained",
         "i told you", "context memory", "global fact"],
        [context_memory],
    ),
    (
        ["ai setup", "refresh rag", "update rag", "re-index", "reindex",
         "rag status", "seed facts", "refresh knowledge", "update knowledge",
         "rebuild index", "ai_setup"],
        [ai_setup],
    ),
    (
        ["report", "dividend report", "holdings report", "transaction summary",
         "portfolio report", "build report", "google finance", "dividend history",
         "dividends received", "my holdings", "my portfolio", "what do i hold",
         "show my shares", "performance report"],
        [report_builder, mcp_bridge],
    ),
    (
        ["tm1 report", "trial balance report", "natural language report",
         "build tm1 report", "resolve element", "report cube"],
        [mcp_bridge],
    ),
]

# Build per-module schema lists once at startup
_MODULE_ANTHROPIC: dict[int, list[dict]] = {}
_MODULE_OPENAI: dict[int, list[dict]] = {}
for _mod in _SKILL_MODULES:
    _mid = id(_mod)
    _MODULE_ANTHROPIC[_mid] = list(_mod.TOOL_SCHEMAS)
    _MODULE_OPENAI[_mid] = [_to_openai_schema(s) for s in _mod.TOOL_SCHEMAS]


def route_tools_for_message(user_message: str) -> tuple[list[dict], list[dict]]:
    """Return (anthropic_schemas, openai_schemas) relevant to *user_message*.

    Always includes core modules (mcp_bridge, widget_generation).
    Adds extra modules only when keywords match. Falls back to ALL tools if
    nothing matches beyond the always-on set (safety net).
    """
    lower = (user_message or "").lower()
    selected_ids: set[int] = {id(m) for m in _ALWAYS_MODULES}

    for keywords, modules in _KEYWORD_ROUTES:
        if any(kw in lower for kw in keywords):
            for m in modules:
                selected_ids.add(id(m))

    # Safety: if only always-modules matched, send everything so the model
    # isn't limited on ambiguous queries.
    if selected_ids == {id(m) for m in _ALWAYS_MODULES}:
        return ANTHROPIC_SCHEMAS, OPENAI_SCHEMAS

    anth: list[dict] = []
    oai: list[dict] = []
    for mid in selected_ids:
        anth.extend(_MODULE_ANTHROPIC.get(mid, []))
        oai.extend(_MODULE_OPENAI.get(mid, []))
    return anth, oai


# ---------------------------------------------------------------------------
# Tool result helpers
# ---------------------------------------------------------------------------

MAX_RESULT_CHARS = 6000

def tool_result_to_str(result: Any, max_chars: int = MAX_RESULT_CHARS) -> str:
    """Serialise a tool result to a string for API tool_result content.
    Truncates large results to *max_chars* to avoid blowing up context.
    """
    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, default=str, indent=2)
        except Exception:
            text = str(result)

    if len(text) > max_chars:
        return text[:max_chars] + "\n... (truncated)"
    return text


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def call_tool(name: str, args: dict) -> Any:
    """
    Call a registered tool function by name with the given args dict.
    Returns the function result or an error dict on failure.
    """
    func = _FUNCTIONS.get(name)
    if not func:
        log.warning("Unknown tool called: %s", name, extra={"tool": name})
        return {"error": f"Unknown tool: '{name}'. Available: {sorted(_FUNCTIONS.keys())}"}

    t0 = time.monotonic()
    try:
        result = func(**args)
        duration = int((time.monotonic() - t0) * 1000)
        if isinstance(result, dict) and "error" in result:
            log.error(
                "Tool %s returned error: %s", name, result["error"],
                extra={"tool": name, "detail": json.dumps(args, default=str),
                       "error_type": "tool_result_error", "duration_ms": duration},
            )
        else:
            log.info("Tool %s OK (%dms)", name, duration,
                     extra={"tool": name, "duration_ms": duration})
        return result
    except TypeError as e:
        duration = int((time.monotonic() - t0) * 1000)
        log.error("Invalid args for %s: %s", name, e,
                  extra={"tool": name, "detail": json.dumps(args, default=str),
                         "error_type": "invalid_args", "duration_ms": duration},
                  exc_info=True)
        return {"error": f"Invalid arguments for {name}: {e}"}
    except Exception as e:
        duration = int((time.monotonic() - t0) * 1000)
        log.error("Tool %s exception: %s", name, e,
                  extra={"tool": name, "detail": json.dumps(args, default=str),
                         "error_type": type(e).__name__, "duration_ms": duration},
                  exc_info=True)
        return {"error": f"{type(e).__name__}: {e}"}


def list_tool_names() -> list[str]:
    return sorted(_FUNCTIONS.keys())
