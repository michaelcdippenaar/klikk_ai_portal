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
import time
import traceback
from dataclasses import dataclass
from typing import Any

from config import settings, get_credential
from logger import log
from system_prompt import build_system_prompt
from tool_registry import (
    ANTHROPIC_SCHEMAS,
    OPENAI_SCHEMAS,
    TOOL_TO_SKILL,
    call_tool,
    route_tools_for_message,
    tool_result_to_str,
)


@dataclass
class ToolCall:
    """Record of a single tool call made during an agent turn."""
    name: str
    input: dict
    result: Any
    tool_use_id: str = ""
    skill: str = ""  # skill module this tool belongs to


# ---------------------------------------------------------------------------
#  Anthropic (Claude) agent loop
# ---------------------------------------------------------------------------

def _trim_history(history: list[dict], max_chars: int = 16000) -> list[dict]:
    """Trim conversation history to fit within token budget.

    Keeps all user messages intact but truncates long assistant messages.
    If still over budget, drops oldest messages.
    """
    trimmed = []
    for m in history:
        content = m.get("content", "")
        if m["role"] == "assistant" and len(content) > 1200:
            content = content[:1200] + "\n... (truncated)"
        trimmed.append({"role": m["role"], "content": content})

    # If total is still too large, drop oldest messages (keep last N)
    total = sum(len(m["content"]) for m in trimmed)
    while total > max_chars and len(trimmed) > 2:
        dropped = trimmed.pop(0)
        total -= len(dropped["content"])

    return trimmed


def _run_anthropic(
    user_message: str, history: list[dict], model: str = ""
) -> tuple[str, list[ToolCall], list[str], dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=get_credential("anthropic_api_key"))
    system = build_system_prompt(user_message)

    messages: list[dict] = _trim_history(history)
    messages.append({"role": "user", "content": user_message})

    routed_anthropic, _, skills_routed = route_tools_for_message(user_message)

    tool_calls_made: list[ToolCall] = []
    final_text = ""
    total_input_tokens = 0
    total_output_tokens = 0

    for _ in range(settings.max_tool_rounds):
        response = client.messages.create(
            model=model or settings.anthropic_model,
            system=system,
            messages=messages,
            tools=routed_anthropic,
            max_tokens=settings.max_tokens,
        )

        # Accumulate token usage across rounds
        if hasattr(response, "usage") and response.usage:
            total_input_tokens += getattr(response.usage, "input_tokens", 0)
            total_output_tokens += getattr(response.usage, "output_tokens", 0)

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
                        ToolCall(block.name, dict(block.input), result, block.id,
                                 skill=TOOL_TO_SKILL.get(block.name, ""))
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

    usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "model": model or settings.anthropic_model,
        "provider": "anthropic",
    }
    return final_text or "(No response generated)", tool_calls_made, skills_routed, usage


# ---------------------------------------------------------------------------
#  OpenAI (GPT) agent loop
# ---------------------------------------------------------------------------

def _run_openai(
    user_message: str, history: list[dict], model: str = ""
) -> tuple[str, list[ToolCall], list[str], dict]:
    import time as _time
    from openai import OpenAI
    from openai import RateLimitError as OpenAIRateLimitError

    client = OpenAI(api_key=get_credential("openai_api_key"))
    system = build_system_prompt(user_message)

    messages: list[dict] = [{"role": "system", "content": system}]
    for m in _trim_history(history):
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    _, routed_openai, skills_routed = route_tools_for_message(user_message)

    tool_calls_made: list[ToolCall] = []
    final_text = ""
    total_input_tokens = 0
    total_output_tokens = 0

    for _ in range(settings.max_tool_rounds):
        last_rate_err = None
        for attempt in range(4):
            try:
                response = client.chat.completions.create(
                    model=model or settings.openai_model,
                    messages=messages,
                    tools=routed_openai,
                    max_tokens=settings.max_tokens,
                )
                break
            except OpenAIRateLimitError as e:
                last_rate_err = e
                wait = min(5.0 * (2**attempt), 60.0)
                log.warning("OpenAI rate limit (429), retry in %.1fs (attempt %d)", wait, attempt + 1)
                _time.sleep(wait)
        else:
            raise last_rate_err or RuntimeError("OpenAI rate limit exceeded after retries")

        # Accumulate token usage across rounds
        if hasattr(response, "usage") and response.usage:
            total_input_tokens += getattr(response.usage, "prompt_tokens", 0)
            total_output_tokens += getattr(response.usage, "completion_tokens", 0)

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
                    ToolCall(func_name, func_args, result, tc.id,
                             skill=TOOL_TO_SKILL.get(func_name, ""))
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

    usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "model": model or settings.openai_model,
        "provider": "openai",
    }
    return final_text or "(No response generated)", tool_calls_made, skills_routed, usage


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


_TM1_TOOL_PREFIXES = ("tm1_", "get_current_period", "verify_model", "test_tm1")

def _should_extract_context(tool_calls: list[ToolCall]) -> bool:
    """Only run extraction when at least one TM1 tool returned real data."""
    for tc in tool_calls:
        if any(tc.name.startswith(p) for p in _TM1_TOOL_PREFIXES):
            if isinstance(tc.result, dict) and "error" not in tc.result:
                return True
    return False


def _auto_extract_context(user_message: str, response_text: str, tool_calls: list[ToolCall]) -> None:
    """
    After each agent turn, use a lightweight LLM call to identify elements
    mentioned and insights learned, then save them via save_element_context.
    Skipped when no TM1 tool returned usable data (saves cost + latency).
    Runs silently — errors are caught and logged but never shown to the user.
    """
    if not _should_extract_context(tool_calls):
        return

    try:
        turn_summary = f"USER: {user_message}\n\nASSISTANT: {response_text}"

        if tool_calls:
            tool_parts = []
            for tc in tool_calls:
                result_str = tool_result_to_str(tc.result)
                if len(result_str) > 1500:
                    result_str = result_str[:1500] + "... (truncated)"
                tool_parts.append(f"TOOL: {tc.name}({json.dumps(tc.input)}) → {result_str}")
            turn_summary += "\n\n" + "\n".join(tool_parts)

        if len(turn_summary) > 6000:
            turn_summary = turn_summary[:6000] + "\n... (truncated)"

        extraction_messages = [
            {"role": "user", "content": f"{_CONTEXT_EXTRACTION_PROMPT}\n\n---\n\n{turn_summary}\n\n---\nReturn JSON array:"},
        ]

        provider = settings.ai_provider.lower()

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=get_credential("anthropic_api_key"))
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                system="You extract element context from conversations. Return ONLY a valid JSON array.",
                messages=extraction_messages,
                max_tokens=1000,
            )
            raw = resp.content[0].text.strip()
        elif provider == "openai":
            import time as _time
            from openai import OpenAI
            from openai import RateLimitError as OpenAIRateLimitError
            client = OpenAI(api_key=get_credential("openai_api_key"))
            last_err = None
            for attempt in range(4):
                try:
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You extract element context from conversations. Return ONLY a valid JSON array."},
                            *extraction_messages,
                        ],
                        max_tokens=1000,
                    )
                    raw = resp.choices[0].message.content or "[]"
                    break
                except OpenAIRateLimitError as e:
                    last_err = e
                    wait = min(5.0 * (2**attempt), 60.0)
                    _time.sleep(wait)
            else:
                raw = "[]"  # best-effort: skip extraction on rate limit
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
#  Auto-extract global facts from conversation
# ---------------------------------------------------------------------------

_GLOBAL_FACT_PROMPT = """You extract general facts and explanations from conversations.
Look for things the user EXPLAINS or TEACHES — definitions, relationships, business context.
Return a JSON array of concise fact strings. Each fact should stand alone and be useful later.

ONLY extract genuine explanations/facts, NOT questions or commands.
If there are no facts to extract, return an empty array: []

Examples of GOOD facts:
- "Absa is a South African bank listed on JSE under ticker ABG"
- "Klikk Group uses fiscal year starting in March"
- "listed_share_src_holdings cube tracks share portfolio positions"

Examples of things to NOT extract:
- "The user asked about Absa" (that's a question, not a fact)
- "Error connecting to TM1" (that's a status, not knowledge)
"""


def _auto_extract_global_facts(user_message: str, response_text: str) -> None:
    """Extract general facts/explanations from the conversation and save to global context."""
    try:
        from context_store import is_available, ensure_tables, save_global_context
        if not is_available():
            return
    except ImportError:
        return

    # Only extract from user messages that look like explanations (heuristic: >20 chars, not a question)
    msg = user_message.strip()
    if len(msg) < 25 or msg.endswith("?"):
        return

    try:
        turn_text = f"USER: {user_message}\n\nASSISTANT: {response_text[:1500]}"
        if len(turn_text) > 4000:
            turn_text = turn_text[:4000]

        extraction_messages = [
            {"role": "user", "content": f"{_GLOBAL_FACT_PROMPT}\n\n---\n\n{turn_text}\n\n---\nReturn JSON array:"},
        ]

        provider = settings.ai_provider.lower()
        raw = "[]"

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=get_credential("anthropic_api_key"))
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                system="Extract facts from conversations. Return ONLY a valid JSON array of strings.",
                messages=extraction_messages,
                max_tokens=500,
            )
            raw = resp.content[0].text.strip()
        elif provider == "openai":
            import time as _time
            from openai import OpenAI, RateLimitError as OpenAIRateLimitError
            client = OpenAI(api_key=get_credential("openai_api_key"))
            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "Extract facts from conversations. Return ONLY a valid JSON array of strings."},
                            *extraction_messages,
                        ],
                        max_tokens=500,
                    )
                    raw = resp.choices[0].message.content or "[]"
                    break
                except OpenAIRateLimitError:
                    _time.sleep(min(5.0 * (2**attempt), 30.0))
            else:
                return

        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else "[]"
            raw = raw.strip()

        facts = json.loads(raw)
        if not isinstance(facts, list):
            return

        ensure_tables()
        for fact in facts:
            if isinstance(fact, str) and len(fact) > 10:
                save_global_context(fact, metadata={"source": "auto_extract"})

    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Public interface — routes to the configured provider
# ---------------------------------------------------------------------------

def run_agent(
    user_message: str,
    history: list[dict],
    model_override: str | None = None,
) -> tuple[str, list[ToolCall], list[str]]:
    """
    Run one conversational turn of the agent.

    After the main response is generated, auto_extract_context() analyses the
    exchange for element-level insights and persists them for future RAG retrieval.

    Args:
        user_message: The user's latest message text.
        history: Prior conversation as list of {"role": "user"|"assistant", "content": str}.
        model_override: Optional model string to override the default (e.g. "gpt-4o", "claude-sonnet-4-6").

    Returns:
        (response_text, tool_calls_made, skills_routed, usage)
    """
    provider = settings.ai_provider.lower()
    model = settings.openai_model if provider == "openai" else settings.anthropic_model

    # Allow frontend to override the model for this turn
    if model_override:
        model = model_override
        # Auto-detect provider from model name
        if model.startswith("claude") or model.startswith("anthropic"):
            provider = "anthropic"
        elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
            provider = "openai"
    log.info("Agent turn started", extra={
        "provider": provider, "model": model,
        "user_message": user_message[:200],
    })

    t0 = time.monotonic()
    if provider == "anthropic":
        response_text, tool_calls, skills_routed, usage = _run_anthropic(user_message, history)
    elif provider == "openai":
        response_text, tool_calls, skills_routed, usage = _run_openai(user_message, history)
    else:
        log.error("Unknown AI provider: %s", provider, extra={"provider": provider})
        return (
            f"Unknown AI_PROVIDER='{provider}' in .env. Set to 'anthropic' or 'openai'.",
            [],
            [],
            {},
        )

    # Collect unique skills actually used (from tool calls)
    skills_used = sorted(set(tc.skill for tc in tool_calls if tc.skill))

    duration = int((time.monotonic() - t0) * 1000)
    usage["duration_ms"] = duration
    log.info(
        "Agent turn complete (%dms, %d tool calls, in=%d out=%d tokens, skills routed: [%s], skills used: [%s])",
        duration, len(tool_calls), usage.get("input_tokens", 0), usage.get("output_tokens", 0),
        ", ".join(skills_routed), ", ".join(skills_used),
        extra={"provider": provider, "model": model, "duration_ms": duration,
               "skills_routed": skills_routed, "skills_used": skills_used,
               "input_tokens": usage.get("input_tokens", 0),
               "output_tokens": usage.get("output_tokens", 0)},
    )

    return response_text, tool_calls, skills_routed, usage


def run_post_processing(user_message: str, response_text: str, tool_calls: list) -> None:
    """Run context extraction as a background task. Called from chat.py
    AFTER the response has been sent to the client."""
    t0 = time.monotonic()
    try:
        _auto_extract_context(user_message, response_text, tool_calls)
    except Exception:
        log.debug("Context extraction failed", exc_info=True)

    try:
        _auto_extract_global_facts(user_message, response_text)
    except Exception:
        log.debug("Global fact extraction failed", exc_info=True)

    dur = int((time.monotonic() - t0) * 1000)
    log.info("Background post-processing: %dms", dur, extra={"duration_ms": dur})
