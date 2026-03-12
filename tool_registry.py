"""
Tool registry — single source of truth for all tool schemas and functions.
Supports both Anthropic and OpenAI tool-calling formats.
"""
from __future__ import annotations

import json
from typing import Any

from mcp_server.skills import (
    tm1_query,
    tm1_metadata,
    tm1_management,
    postgres_query,
    pattern_analysis,
    kpi_monitor,
    validation,
    element_context,
    web_search,
    google_drive,
)

_SKILL_MODULES = [
    tm1_query,
    tm1_metadata,
    tm1_management,
    postgres_query,
    pattern_analysis,
    kpi_monitor,
    validation,
    element_context,
    web_search,
    google_drive,
]

# Anthropic-format schemas (name, description, input_schema)
ANTHROPIC_SCHEMAS: list[dict] = []
for _mod in _SKILL_MODULES:
    ANTHROPIC_SCHEMAS.extend(_mod.TOOL_SCHEMAS)

# name -> callable
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


# OpenAI-format schemas (type: function, function: {name, description, parameters})
OPENAI_SCHEMAS: list[dict] = [_to_openai_schema(s) for s in ANTHROPIC_SCHEMAS]


def call_tool(name: str, args: dict) -> Any:
    """
    Call a registered tool function by name with the given args dict.
    Returns the function result or an error dict on failure.
    """
    func = _FUNCTIONS.get(name)
    if not func:
        return {"error": f"Unknown tool: '{name}'. Available: {sorted(_FUNCTIONS.keys())}"}
    try:
        return func(**args)
    except TypeError as e:
        return {"error": f"Invalid arguments for {name}: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def list_tool_names() -> list[str]:
    return sorted(_FUNCTIONS.keys())


def tool_result_to_str(result: Any) -> str:
    """Serialise a tool result to a string for API tool_result content."""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str, indent=2)
    except Exception:
        return str(result)
