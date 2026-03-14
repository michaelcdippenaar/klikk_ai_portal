"""
Tool registry — single source of truth for all tool schemas and functions.
Supports both Anthropic and OpenAI tool-calling formats.

Optimisation: route_tools_for_message() returns only the subset of tool
schemas relevant to a given user message, reducing token count and
improving tool selection accuracy.

Architecture:
  - mcp_bridge is split into 6 sub-groups for fine-grained routing:
    tm1_metadata, tm1_query, tm1_write, pg_tools, report_builder_mcp, sql_builder
  - widget_generation is keyword-triggered (not always-on)
  - Greetings / simple questions get NO tools (pure prompt response)
  - Each keyword route maps to specific sub-groups, not whole modules
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
    investment_analyst,
    dividend_forecast,
)


# ---------------------------------------------------------------------------
# Sub-groups extracted from mcp_bridge (schemas + functions stay in mcp_bridge)
# ---------------------------------------------------------------------------

class _SchemaGroup:
    """Lightweight wrapper so sub-groups look like skill modules to the router."""
    def __init__(self, name: str, schemas: list[dict], functions: dict[str, Any]):
        self.__name__ = name
        self.TOOL_SCHEMAS = schemas
        self.TOOL_FUNCTIONS = functions


# Build sub-groups from mcp_bridge's internal schema groups
_mcp_funcs = mcp_bridge.TOOL_FUNCTIONS

tm1_metadata = _SchemaGroup(
    "tm1_metadata",
    mcp_bridge.TOOL_SCHEMAS_TM1_METADATA,
    {s["name"]: _mcp_funcs[s["name"]] for s in mcp_bridge.TOOL_SCHEMAS_TM1_METADATA},
)

tm1_query = _SchemaGroup(
    "tm1_query",
    mcp_bridge.TOOL_SCHEMAS_TM1_QUERY,
    {s["name"]: _mcp_funcs[s["name"]] for s in mcp_bridge.TOOL_SCHEMAS_TM1_QUERY},
)

tm1_write = _SchemaGroup(
    "tm1_write",
    mcp_bridge.TOOL_SCHEMAS_TM1_MANAGEMENT,
    {s["name"]: _mcp_funcs[s["name"]] for s in mcp_bridge.TOOL_SCHEMAS_TM1_MANAGEMENT},
)

pg_tools = _SchemaGroup(
    "pg_tools",
    mcp_bridge.TOOL_SCHEMAS_PG,
    {s["name"]: _mcp_funcs[s["name"]] for s in mcp_bridge.TOOL_SCHEMAS_PG},
)

report_builder_mcp = _SchemaGroup(
    "report_builder_mcp",
    mcp_bridge.TOOL_SCHEMAS_TM1_REPORT_BUILDER,
    {s["name"]: _mcp_funcs[s["name"]] for s in mcp_bridge.TOOL_SCHEMAS_TM1_REPORT_BUILDER},
)

sql_builder = _SchemaGroup(
    "sql_builder",
    mcp_bridge.TOOL_SCHEMAS_SQL_BUILDER,
    {s["name"]: _mcp_funcs[s["name"]] for s in mcp_bridge.TOOL_SCHEMAS_SQL_BUILDER},
)


# ---------------------------------------------------------------------------
# All modules — for dispatch (call_tool always works, regardless of routing)
# ---------------------------------------------------------------------------

_ALL_MODULES = [
    tm1_metadata, tm1_query, tm1_write, pg_tools, report_builder_mcp, sql_builder,
    tm1_rest_api, pattern_analysis, kpi_monitor, validation,
    element_context, web_search, google_drive, widget_generation,
    paw_integration, session_review, financials_data, statistics,
    share_metrics, context_memory, report_builder, ai_setup,
    investment_analyst, dividend_forecast,
]

# Full schema lists (used as reference; not sent to model — routing picks subsets)
ANTHROPIC_SCHEMAS: list[dict] = []
for _mod in _ALL_MODULES:
    ANTHROPIC_SCHEMAS.extend(_mod.TOOL_SCHEMAS)

_FUNCTIONS: dict[str, Any] = {}
for _mod in _ALL_MODULES:
    _FUNCTIONS.update(_mod.TOOL_FUNCTIONS)

TOOL_TO_SKILL: dict[str, str] = {}
for _mod in _ALL_MODULES:
    _skill_name = _mod.__name__.rsplit(".", 1)[-1] if hasattr(_mod, '__name__') else _mod.__name__
    for _schema in _mod.TOOL_SCHEMAS:
        TOOL_TO_SKILL[_schema["name"]] = _skill_name


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
# Tool routing — keyword-based sub-group selection
# ---------------------------------------------------------------------------

# Minimal core: tm1_metadata + tm1_query covers "what cubes/dims exist" + MDX
_CORE_MODULES = [tm1_metadata, tm1_query]

# Each route maps keywords -> specific sub-groups (not whole mcp_bridge)
_KEYWORD_ROUTES: list[tuple[list[str], list]] = [
    # --- TM1 admin / REST API ---
    (
        ["server status", "message log", "transaction log", "thread", "session",
         "sandbox", "error log", "rest api", "server health", "server version",
         "who is logged", "active user"],
        [tm1_rest_api],
    ),
    # --- TM1 write operations ---
    (
        ["write value", "write cell", "write back", "data entry", "write to",
         "execute view", "named view", "run view", "rpt_", "report view",
         "update attribute", "update element", "forecast cell"],
        [tm1_write, tm1_rest_api],
    ),
    # --- TI processes ---
    (
        ["process", "chore", "ti ", "turbointegrator", "run process",
         "execute process", "schedule"],
        [tm1_write],
    ),
    # --- PostgreSQL / share data ---
    (
        ["postgres", "sql", "xero", "gl data", "general ledger", "database",
         "pg ", "trial_balance import"],
        [pg_tools, sql_builder],
    ),
    (
        ["share", "stock", "portfolio", "investment", "dividend", "price history",
         "holdings", "investec", "symbol", "pricepoint"],
        [pg_tools, investment_analyst],
    ),
    # --- Financials RAG / vector search ---
    (
        ["vectorized", "vector search", "financials data", "data guide",
         "how data fits", "corpora", "rag financials", "klikk financials",
         "trail balance", "xero cube", "consolidate journals"],
        [financials_data],
    ),
    # --- Pattern / anomaly ---
    (
        ["anomal", "pattern", "outlier", "variance", "spike", "unusual"],
        [pattern_analysis, tm1_query],
    ),
    # --- KPI / current period ---
    (
        ["kpi", "metric", "threshold", "alert", "monitor", "target",
         "current month", "current year", "current period", "financial year"],
        [kpi_monitor],
    ),
    # --- Validation ---
    (
        ["validate", "verification", "check model", "verify", "reconcil"],
        [validation],
    ),
    # --- Element context / memory ---
    (
        ["element context", "save context", "what do we know about",
         "index dimension", "index element"],
        [element_context],
    ),
    # --- Web search ---
    (
        ["search", "google", "look up", "internet", "stock price",
         "current price", "news", "web", "article", "publish article",
         "fetch article", "read article"],
        [web_search],
    ),
    # --- Google Drive ---
    (
        ["drive", "google drive", "document", "gdrive"],
        [google_drive],
    ),
    # --- PAW ---
    (
        ["paw", "planning analytics workspace", "embed", "paw book",
         "paw view", "writeback", "view mdx", "query state", "get view data",
         "current view", "view query state", "extract values", "view data"],
        [paw_integration],
    ),
    # --- Session review ---
    (
        ["session", "chat log", "review session", "review chat",
         "improve skill", "improve tool", "chat history log"],
        [session_review],
    ),
    # --- Statistics ---
    (
        ["forecast trend", "trend analysis", "time series", "history predict",
         "statistics", "linear trend", "growth rate", "volatility"],
        [statistics],
    ),
    # --- Share metrics (DPS, yield, etc.) ---
    (
        ["dividend per share", "payout ratio", "eps", "dividend yield",
         "share metrics", "dps", "retention ratio", "dividends per share"],
        [share_metrics, pg_tools],
    ),
    # --- Context memory ---
    (
        ["remember", "global context", "save fact", "what did i say",
         "past conversation", "what do we know", "recall", "explained",
         "i told you", "context memory", "global fact"],
        [context_memory],
    ),
    # --- AI setup / RAG admin ---
    (
        ["ai setup", "refresh rag", "update rag", "re-index", "reindex",
         "rag status", "seed facts", "refresh knowledge", "update knowledge",
         "rebuild index", "ai_setup"],
        [ai_setup],
    ),
    # --- Investment analyst ---
    (
        ["investment analyst", "look up share", "share lookup", "find share",
         "upcoming dividend", "which stock", "which share", "p/e ratio",
         "pe ratio", "analyst recommendation", "price target",
         "share data", "share cube", "share research",
         "portfolio summary", "investment overview", "screen share",
         "filter stock", "filter share", "yield above",
         "ratio below", "return on investment", "roi", "performance",
         "compare share", "compare stock", "vs ", " versus ",
         "dividend growth", "dividend analysis", "how has",
         "price return", "total return", "yield on cost", "cagr"],
        [investment_analyst, pg_tools],
    ),
    # --- Charts / visualisation (adds widget_generation) ---
    (
        ["chart", "graph", "line chart", "bar chart", "pie chart", "visuali",
         "plot", "trend chart", "price chart", "price history chart",
         "show", "display", "dashboard", "widget", "kpicard", "cube viewer",
         "pivot", "dimension tree", "set builder", "mdx editor", "sql editor"],
        [widget_generation],
    ),
    # --- Pre-built reports ---
    (
        ["report", "dividend report", "holdings report", "transaction summary",
         "portfolio report", "build report", "google finance", "dividend history",
         "dividends received", "my holdings", "my portfolio", "what do i hold",
         "show my shares", "performance report"],
        [report_builder, pg_tools],
    ),
    # --- Dividend forecast ---
    (
        ["dividend forecast", "dividend adjustment", "declared dividend",
         "adjust dps", "budget dps", "dividend budget", "dps adjustment",
         "declared dps", "forecast dps", "pln_forecast", "dividend calendar"],
        [dividend_forecast, tm1_query],
    ),
    # --- TM1 report builder (natural language → MDX) ---
    (
        ["tm1 report", "trial balance report", "natural language report",
         "build tm1 report", "resolve element", "report cube"],
        [report_builder_mcp, tm1_query],
    ),
    # --- General TM1 / financial planning ---
    (
        ["trial balance", "balance sheet", "income statement", "profit and loss",
         "p&l", "cash flow", "cube", "mdx", "dimension", "hierarchy",
         "element", "subset", "consolidat", "account", "entity", "version",
         "actual", "budget", "budget forecast", "period", "month",
         "january", "february", "march", "april", "may", "june",
         "july", "august", "september", "october", "november", "december",
         "klikk group", "klikk pty", "tremly", "gl_src",
         "tm1", "planning analytics"],
        [tm1_metadata, tm1_query, report_builder_mcp],
    ),
]


# ---------------------------------------------------------------------------
# Simple-message detection (no tools needed)
# ---------------------------------------------------------------------------

_GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|good morning|good afternoon|good evening|thanks|thank you|"
    r"ok|okay|sure|yes|no|what skills|what tools|what can you do|who are you|"
    r"help me|how are you)\b",
    re.IGNORECASE,
)


def _is_simple_message(msg: str) -> bool:
    """Return True if the message is a greeting or meta-question that doesn't need tools."""
    stripped = msg.strip()
    if len(stripped) < 50 and _GREETING_PATTERNS.match(stripped):
        return True
    return False


# ---------------------------------------------------------------------------
# Build per-module schema lists once at startup
# ---------------------------------------------------------------------------

_MODULE_ANTHROPIC: dict[int, list[dict]] = {}
_MODULE_OPENAI: dict[int, list[dict]] = {}
for _mod in _ALL_MODULES:
    _mid = id(_mod)
    _MODULE_ANTHROPIC[_mid] = list(_mod.TOOL_SCHEMAS)
    _MODULE_OPENAI[_mid] = [_to_openai_schema(s) for s in _mod.TOOL_SCHEMAS]


def route_tools_for_message(user_message: str) -> tuple[list[dict], list[dict], list[str]]:
    """Return (anthropic_schemas, openai_schemas, skill_names) relevant to *user_message*.

    - For greetings/simple questions: returns empty tool lists (no tools needed).
    - Core modules (tm1_metadata, tm1_query) are added when any keyword matches.
    - widget_generation is only added when visualisation keywords are present.
    - Falls back to a small default set when nothing matches.
    """
    msg = (user_message or "").strip()
    lower = msg.lower()

    # No-tools path: greetings and simple meta-questions
    if _is_simple_message(msg):
        log.info("Tool routing: no tools (simple message)")
        return [], [], []

    selected_ids: set[int] = set()

    # Regex-based routes (patterns that can't be simple substring matches)
    if re.search(r"\bwrite\s+\d", lower):
        selected_ids.add(id(tm1_write))

    for keywords, modules in _KEYWORD_ROUTES:
        if any(kw in lower for kw in keywords):
            for m in modules:
                selected_ids.add(id(m))

    # If keywords matched, always include core TM1 tools (metadata + query)
    if selected_ids:
        for m in _CORE_MODULES:
            selected_ids.add(id(m))
    else:
        # Fallback: core TM1 + report builder + investment analyst (covers most asks)
        fallback = [tm1_metadata, tm1_query, report_builder_mcp, investment_analyst, pg_tools]
        selected_ids = {id(m) for m in fallback}
        names = sorted(m.__name__ for m in fallback)
        log.info("Tool routing: fallback set (no keyword match): %s", ", ".join(names))

    # Collect matched skill names
    _id_to_name = {id(m): getattr(m, '__name__', '?').rsplit(".", 1)[-1] for m in _ALL_MODULES}
    skill_names = sorted(_id_to_name[mid] for mid in selected_ids if mid in _id_to_name)
    log.info("Tool routing: %s (%d schemas)", ", ".join(skill_names), sum(len(_MODULE_ANTHROPIC.get(mid, [])) for mid in selected_ids))

    anth: list[dict] = []
    oai: list[dict] = []
    for mid in selected_ids:
        anth.extend(_MODULE_ANTHROPIC.get(mid, []))
        oai.extend(_MODULE_OPENAI.get(mid, []))
    return anth, oai, skill_names


# ---------------------------------------------------------------------------
# Tool result helpers
# ---------------------------------------------------------------------------

MAX_RESULT_CHARS = 2800

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
