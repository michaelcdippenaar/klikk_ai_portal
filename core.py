"""
Agent core — conversation loop with tool use.
Supports both Anthropic (Claude) and OpenAI (GPT) as providers.

After each turn, auto_extract_context() analyses the conversation to identify
TM1 elements mentioned and insights learned, then persists them via
save_element_context() for future RAG retrieval.

Usage:
    from core import run_agent
    response, tool_calls = run_agent("What cubes exist?", history=[])
"""
from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from typing import Any

from config import settings
from system_prompt import build_system_prompt
from tool_registry import (
    ANTHROPIC_SCHEMAS,
    OPENAI_SCHEMAS,
    call_tool,
    tool_result_to_str,
)


@dataclass
class ToolCall:
    """Record of a single tool call made during an agent turn."""
    name: str
    input: dict
    result: Any
    tool_use_id: str = ""


# ---------------------------------------------------------------------------
#  Anthropic (Claude) agent loop
# ---------------------------------------------------------------------------

def _run_anthropic(
    user_message: str, history: list[dict]
) -> tuple[str, list[ToolCall]]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    system = build_system_prompt(user_message)

    messages: list[dict] = [
        {"role": m["role"], "content": m["content"]} for m in history
    ]
    messages.append({"role": "user", "content": user_message})

    tool_calls_made: list[ToolCall] = []
    final_text = ""

    for _ in range(settings.max_tool_rounds):
        response = client.messages.create(
            model=settings.anthropic_model,
            system=system,
            messages=messages,
            tools=ANTHROPIC_SCHEMAS,
            max_tokens=settings.max_tokens,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = call_tool(block.name, block.input)
                    tool_calls_made.append(
                        ToolCall(block.name, dict(block.input), result, block.id)
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result_to_str(result),
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            break

    return final_text or "(No response generated)", tool_calls_made


# ---------------------------------------------------------------------------
#  OpenAI (GPT) agent loop
# ---------------------------------------------------------------------------

def _run_openai(
    user_message: str, history: list[dict]
) -> tuple[str, list[ToolCall]]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    system = build_system_prompt(user_message)

    messages: list[dict] = [{"role": "system", "content": system}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    tool_calls_made: list[ToolCall] = []
    final_text = ""

    for _ in range(settings.max_tool_rounds):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=OPENAI_SCHEMAS,
            max_tokens=settings.max_tokens,
        )
        choice = response.choices[0]

        if choice.finish_reason == "stop":
            final_text = choice.message.content or ""
            break

        if choice.finish_reason == "tool_calls":
            # Append the assistant message (contains tool_calls)
            messages.append(choice.message)

            for tc in choice.message.tool_calls:
                func_name = tc.function.name
                try:
                    func_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                result = call_tool(func_name, func_args)
                tool_calls_made.append(
                    ToolCall(func_name, func_args, result, tc.id)
                )
                # Append tool result message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result_to_str(result),
                })
        else:
            # Unexpected finish reason
            final_text = choice.message.content or ""
            break

    return final_text or "(No response generated)", tool_calls_made


# ---------------------------------------------------------------------------
#  Auto-extract element context after each turn
# ---------------------------------------------------------------------------

_CONTEXT_EXTRACTION_PROMPT = """You are a context extraction assistant for a TM1 financial planning model.
Analyse the following conversation exchange and identify any specific TM1 dimension elements
that were discussed, along with meaningful insights or context learned about them.

ONLY extract context if there is a genuine insight about a SPECIFIC element — not general questions.
Return a JSON array of objects, each with:
- "dimension": the dimension name (e.g. "account", "entity", "cashflow_activity", "listed_share", "month", "version")
- "element": the specific element name as it appears in TM1
- "context": a concise description of what was learned about this element

If no specific element insights were discussed, return an empty array: []

Examples of GOOD extractions:
- {"dimension": "account", "element": "acc_001", "context": "Main office rent account for Klikk HQ, typically R45K/month"}
- {"dimension": "entity", "element": "klikk_properties", "context": "Holds all rental properties, main revenue driver"}
- {"dimension": "cashflow_activity", "element": "operating_payments", "context": "Includes rent, salaries, and operational costs"}

Examples of things to NOT extract (too generic):
- General questions like "What cubes exist?"
- Dimension-level facts without a specific element
- Tool errors or connection issues
"""


def _auto_extract_context(user_message: str, response_text: str, tool_calls: list[ToolCall]) -> None:
    """
    After each agent turn, use a lightweight LLM call to identify elements
    mentioned and insights learned, then save them via save_element_context.
    Runs silently — errors are caught and logged but never shown to the user.
    """
    try:
        # Build a summary of what happened this turn
        turn_summary = f"USER: {user_message}\n\nASSISTANT: {response_text}"

        # Include tool call results (truncated) for richer context
        if tool_calls:
            tool_parts = []
            for tc in tool_calls:
                result_str = tool_result_to_str(tc.result)
                # Truncate large results to keep the extraction prompt manageable
                if len(result_str) > 1500:
                    result_str = result_str[:1500] + "... (truncated)"
                tool_parts.append(f"TOOL: {tc.name}({json.dumps(tc.input)}) → {result_str}")
            turn_summary += "\n\n" + "\n".join(tool_parts)

        # Cap total summary to avoid excessive token usage
        if len(turn_summary) > 6000:
            turn_summary = turn_summary[:6000] + "\n... (truncated)"

        extraction_messages = [
            {"role": "user", "content": f"{_CONTEXT_EXTRACTION_PROMPT}\n\n---\n\n{turn_summary}\n\n---\nReturn JSON array:"},
        ]

        provider = settings.ai_provider.lower()

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            resp = client.messages.create(
                model=settings.anthropic_model,
                system="You extract element context from conversations. Return ONLY a valid JSON array.",
                messages=extraction_messages,
                max_tokens=1000,
            )
            raw = resp.content[0].text.strip()
        elif provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You extract element context from conversations. Return ONLY a valid JSON array."},
                    *extraction_messages,
                ],
                max_tokens=1000,
            )
            raw = resp.choices[0].message.content or "[]"
        else:
            return

        # Parse the JSON — handle markdown code blocks if the LLM wraps it
        raw = raw.strip()
        if raw.startswith("```"):
            # Strip markdown code fences
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else "[]"
            raw = raw.strip()

        extractions = json.loads(raw)
        if not isinstance(extractions, list):
            return

        # Save each extracted context note
        from mcp_server.skills.element_context import save_element_context
        for item in extractions:
            if isinstance(item, dict) and all(k in item for k in ("dimension", "element", "context")):
                save_element_context(
                    dimension_name=str(item["dimension"]),
                    element_name=str(item["element"]),
                    context_note=str(item["context"]),
                )

    except Exception:
        # Silently swallow — context extraction is best-effort
        # Uncomment for debugging:
        # traceback.print_exc()
        pass


# ---------------------------------------------------------------------------
#  Public interface — routes to the configured provider
# ---------------------------------------------------------------------------

def run_agent(
    user_message: str,
    history: list[dict],
) -> tuple[str, list[ToolCall]]:
    """
    Run one conversational turn of the agent.

    After the main response is generated, auto_extract_context() analyses the
    exchange for element-level insights and persists them for future RAG retrieval.

    Args:
        user_message: The user's latest message text.
        history: Prior conversation as list of {"role": "user"|"assistant", "content": str}.

    Returns:
        (response_text, tool_calls_made)
    """
    provider = settings.ai_provider.lower()
    if provider == "anthropic":
        response_text, tool_calls = _run_anthropic(user_message, history)
    elif provider == "openai":
        response_text, tool_calls = _run_openai(user_message, history)
    else:
        return (
            f"Unknown AI_PROVIDER='{provider}' in .env. Set to 'anthropic' or 'openai'.",
            [],
        )

    # Auto-extract element context (best-effort, non-blocking to the user)
    try:
        _auto_extract_context(user_message, response_text, tool_calls)
    except Exception:
        pass

    return response_text, tool_calls
