"""
WebSocket chat endpoint — wraps the existing agent core.
Streams tool calls and final response to the Vue frontend.

Each session's full conversation (user messages, tool calls, assistant
responses) is persisted to a human-readable text file under
  <project_root>/logs/chat_sessions/<session_id>.txt
Files are append-only so they survive server restarts.
"""
from __future__ import annotations

import asyncio
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from logger import log
from auth_middleware import verify_ws_token

router = APIRouter()

# In-memory chat histories keyed by session ID
_sessions: dict[str, list[dict]] = {}

# ---------------------------------------------------------------------------
#  Per-session text-file logging
# ---------------------------------------------------------------------------

_CHAT_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "chat_sessions"
_CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _safe_session_id(session_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)


def _log_path(session_id: str) -> Path:
    return _CHAT_LOG_DIR / f"{_safe_session_id(session_id)}.txt"


def _history_path(session_id: str) -> Path:
    return _CHAT_LOG_DIR / f"{_safe_session_id(session_id)}.json"


def _load_session_history(session_id: str) -> list[dict]:
    """Load message history from disk if present."""
    path = _history_path(session_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("messages", [])
    except Exception:
        return []


def _save_session_history(session_id: str, messages: list[dict], paw_context: dict | None = None) -> None:
    """Persist message history (and optional PAW context) to disk."""
    path = _history_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"session_id": session_id, "messages": messages}
    if paw_context:
        payload["paw_context"] = paw_context
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _append_to_log(session_id: str, text: str) -> None:
    try:
        with open(_log_path(session_id), "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        log.debug("Failed to write chat log for session %s", session_id, exc_info=True)


def _log_turn(
    session_id: str,
    user_message: str,
    response_text: str,
    tool_calls: list,
    widgets: list,
    error: str | None = None,
) -> None:
    """Append one full turn (user + tools + assistant) to the session log."""
    sep = "=" * 72
    lines = [
        f"\n{sep}\n",
        f"[{_ts()}]  Turn {_turn_count(session_id)}\n",
        f"{sep}\n\n",
        f"USER:\n{user_message}\n\n",
    ]

    if tool_calls:
        lines.append("TOOL CALLS:\n")
        for tc in tool_calls:
            name = tc.get("name", tc.name) if hasattr(tc, "name") else tc.get("name", "?")
            inp = tc.get("input", getattr(tc, "input", {}))
            res = tc.get("result", getattr(tc, "result", ""))
            res_str = json.dumps(res, default=str, indent=2) if not isinstance(res, str) else res
            if len(res_str) > 2000:
                res_str = res_str[:2000] + "\n  ... (truncated)"
            lines.append(f"  > {name}({json.dumps(inp, default=str)})\n")
            lines.append(f"    Result: {res_str}\n\n")

    if widgets:
        lines.append(f"WIDGETS CREATED: {len(widgets)}\n")
        for w in widgets:
            lines.append(f"  - {w.get('type', '?')}: {w.get('title', '?')} (id={w.get('id', '?')})\n")
        lines.append("\n")

    if error:
        lines.append(f"ERROR:\n{error}\n\n")

    lines.append(f"ASSISTANT:\n{response_text}\n")

    _append_to_log(session_id, "".join(lines))


_turn_counters: dict[str, int] = {}


def _turn_count(session_id: str) -> int:
    _turn_counters[session_id] = _turn_counters.get(session_id, 0) + 1
    return _turn_counters[session_id]


def _serialize(obj: Any) -> str:
    """JSON serialize with fallback for non-serializable types."""
    try:
        return json.dumps(obj, default=str, indent=None)
    except Exception:
        return str(obj)


def _store_turn_in_pgvector(
    session_id: str, user_msg: str, assistant_msg: str,
    paw_ctx: dict | None,
) -> None:
    """Best-effort: embed and store user + assistant turns in pgvector conversation_context."""
    import time as _t
    t0 = _t.monotonic()
    try:
        from context_store import is_available, ensure_tables, save_conversation_turn
        if not is_available():
            log.debug("pgvector context store: not available (skipped)")
            return
        ensure_tables()
        meta = dict(paw_ctx) if paw_ctx else {}
        meta.pop("queryState", None)
        save_conversation_turn(session_id, "user", user_msg, metadata=meta)
        if assistant_msg:
            save_conversation_turn(session_id, "assistant", assistant_msg, metadata=meta)
        dur = int((_t.monotonic() - t0) * 1000)
        log.info("pgvector context store: 2 turns saved (%dms)", dur,
                 extra={"session_id": session_id, "duration_ms": dur})
    except Exception:
        dur = int((_t.monotonic() - t0) * 1000)
        log.warning("pgvector context store failed (%dms)", dur, exc_info=True)


def _run_agent_sync(prompt: str, history: list[dict], model: str = "") -> tuple[str, list]:
    """Run the agent synchronously (existing core.run_agent)."""
    from core import run_agent
    return run_agent(prompt, history, model_override=model or None)


@router.websocket("/chat")
async def websocket_chat(ws: WebSocket, token: str = Query(default=None)):
    """
    WebSocket protocol:

    Client → Server:
      { "type": "message", "content": "...", "session_id": "..." }

    Server → Client (sequence):
      { "type": "thinking" }
      { "type": "tool_call", "name": "...", "input": {...}, "id": "..." }
      { "type": "tool_result", "name": "...", "result": ..., "id": "..." }
      { "type": "response", "content": "...", "tool_calls": [...], "widgets": [...] }
      { "type": "error", "message": "..." }

    Authentication: pass JWT token via query parameter ?token=<jwt>
    """
    # Validate auth before accepting connection
    user = await verify_ws_token(token)
    if not user:
        await ws.close(code=4001, reason="Authentication required")
        return

    await ws.accept()
    ws.state.user = user

    try:
        while True:
            data = await ws.receive_json()

            if data.get("type") != "message":
                continue

            content = data.get("content", "").strip()
            session_id = data.get("session_id", "default")
            model_override = data.get("model", "")
            widget_context = data.get("widget_context")  # optional: { "summary", "cubeName", "serverName", "queryState" }

            if not content:
                continue

            # Parse PAW context from widget_context (parentStore fields sent by frontend)
            paw_ctx: dict | None = None
            if isinstance(widget_context, dict):
                cn = widget_context.get("cubeName") or widget_context.get("cube")
                sn = widget_context.get("serverName") or widget_context.get("server")
                qs = widget_context.get("queryState")
                vn = widget_context.get("viewName")
                if cn or sn or qs:
                    paw_ctx = {}
                    if cn: paw_ctx["cubeName"] = cn
                    if sn: paw_ctx["serverName"] = sn
                    if vn: paw_ctx["viewName"] = vn
                    if qs: paw_ctx["queryState"] = qs

                # Persist current PAW view to agent "local DB" so tools can get view MDX/data
                if qs and cn and sn:
                    try:
                        from agent_view_store import save_agent_current_view
                        save_agent_current_view(cn, sn, qs)
                    except Exception:
                        pass

            # Prepend PAW widget context so the agent sees what the user is viewing (cube, dimensions, selections)
            prompt = content
            if isinstance(widget_context, dict) and widget_context.get("summary"):
                prompt = f"{widget_context['summary']}\n\nUser message: {content}"

            # Get or create session history (load from disk if not in memory)
            if session_id not in _sessions:
                loaded = _load_session_history(session_id)
                _sessions[session_id] = loaded
                if not loaded:
                    header = (
                        f"Chat Session: {session_id}\n"
                        f"Started:      {_ts()}\n"
                        f"User:         {getattr(ws.state, 'user', {}).get('username', 'unknown')}\n"
                        f"{'=' * 72}\n"
                    )
                    _append_to_log(session_id, header)
            history = _sessions[session_id]

            # Add user message to history (store original content for display)
            history.append({"role": "user", "content": content})

            # Notify client we're thinking
            await ws.send_json({"type": "thinking"})
            import time as _time
            _turn_t0 = _time.monotonic()

            try:
                # Run agent in thread pool (it's synchronous); pass prompt with widget context
                loop = asyncio.get_event_loop()
                response_text, tool_calls = await loop.run_in_executor(
                    None, _run_agent_sync, prompt, history[:-1], model_override
                )
                _agent_ms = int((_time.monotonic() - _turn_t0) * 1000)
                log.info("Chat turn: agent completed in %dms (%d tool calls)",
                         _agent_ms, len(tool_calls),
                         extra={"session_id": session_id, "duration_ms": _agent_ms})

                # Extract widgets from tool calls
                widgets = []
                serialized_calls = []
                has_errors = False
                error_details = []
                for tc in tool_calls:
                    result = tc.result if isinstance(tc.result, (dict, list, str)) else str(tc.result)
                    call_data = {
                        "name": tc.name,
                        "input": tc.input,
                        "result": result,
                        "id": getattr(tc, "tool_use_id", ""),
                    }
                    # Detect tool-level errors
                    if isinstance(result, dict) and result.get("error"):
                        call_data["is_error"] = True
                        has_errors = True
                        error_details.append(f"{tc.name}: {result['error']}")
                    serialized_calls.append(call_data)

                    # Send each tool call as it happens
                    await ws.send_text(json.dumps({
                        "type": "tool_call",
                        "name": tc.name,
                        "input": tc.input,
                        "id": getattr(tc, "tool_use_id", ""),
                    }, default=str))

                    # Check if any tool returned widget(s) (widget_generation, paw_integration, report_builder)
                    if isinstance(tc.result, dict) and tc.result.get("status") == "widget_created":
                        if "widget" in tc.result:
                            widgets.append(tc.result["widget"])
                        if "widgets" in tc.result and isinstance(tc.result["widgets"], list):
                            widgets.extend(tc.result["widgets"])

                # Add assistant message to history (with error flag if any tools failed)
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": response_text}
                if has_errors:
                    assistant_msg["has_errors"] = True
                    assistant_msg["error_details"] = error_details
                history.append(assistant_msg)

                # Keep history manageable (last 40 messages)
                if len(history) > 40:
                    _sessions[session_id] = history[-40:]

                # Persist full history to JSON (for multiple chats / recall), with PAW context
                _save_session_history(session_id, _sessions[session_id], paw_context=paw_ctx)

                # Persist turn to session log file (flag tool errors)
                _log_turn(session_id, content, response_text,
                          serialized_calls, widgets,
                          error="\n".join(error_details) if error_details else None)

                # Store both turns in pgvector conversation context (best-effort)
                _store_turn_in_pgvector(session_id, content, response_text, paw_ctx)

                _total_ms = int((_time.monotonic() - _turn_t0) * 1000)
                log.info("Chat turn TOTAL: %dms (agent: %dms, post-processing: %dms)",
                         _total_ms, _agent_ms, _total_ms - _agent_ms,
                         extra={"session_id": session_id, "duration_ms": _total_ms})

                # Send final response (use send_text with default=str to handle date/decimal)
                response_payload: dict[str, Any] = {
                    "type": "response",
                    "content": response_text,
                    "tool_calls": serialized_calls,
                    "widgets": widgets,
                }
                if has_errors:
                    response_payload["has_errors"] = True
                    response_payload["error_count"] = len(error_details)
                await ws.send_text(json.dumps(response_payload, default=str))

                # Fire-and-forget post-processing (after response already sent)
                try:
                    from core import run_post_processing
                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(None, run_post_processing, content, response_text, tool_calls)
                except Exception:
                    log.debug("Failed to schedule post-processing", exc_info=True)

            except Exception as e:
                log.error("Chat agent error: %s", e,
                          extra={"session_id": session_id, "error_type": type(e).__name__,
                                 "user_message": content[:200]},
                          exc_info=True)
                _log_turn(session_id, content, "", [], [],
                          error=f"{type(e).__name__}: {e}")
                await ws.send_json({
                    "type": "error",
                    "message": f"{type(e).__name__}: {str(e)}",
                })

    except WebSocketDisconnect:
        log.debug("WebSocket disconnected: %s", session_id)
    except Exception:
        log.error("WebSocket unexpected error", exc_info=True)


@router.post("/chat/clear")
async def clear_chat(session_id: str = "default"):
    """Clear chat history for a session (memory and disk)."""
    _sessions.pop(session_id, None)
    path = _history_path(session_id)
    if path.exists():
        path.unlink()
    return {"status": "cleared", "session_id": session_id}


@router.get("/chat/history")
async def get_history(session_id: str = "default"):
    """Get chat history for a session (loads from disk if not in memory).
    Also returns paw_context if stored."""
    if session_id not in _sessions:
        _sessions[session_id] = _load_session_history(session_id)
    # Load paw_context from disk (it's stored alongside messages)
    paw_context = None
    path = _history_path(session_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
                paw_context = disk_data.get("paw_context")
        except Exception:
            pass
    return {"session_id": session_id, "messages": _sessions.get(session_id, []), "paw_context": paw_context}


@router.get("/chat/sessions")
async def list_sessions():
    """List saved chat session ids (for multiple chats)."""
    if not _CHAT_LOG_DIR.exists():
        return {"sessions": [], "count": 0}
    sessions = []
    for path in _CHAT_LOG_DIR.glob("*.json"):
        session_id = path.stem
        sessions.append({"id": session_id, "file": path.name})
    sessions.sort(key=lambda x: x["id"])
    return {"sessions": sessions, "count": len(sessions)}


@router.post("/chat/sessions")
async def create_session():
    """Create a new chat session; returns new session_id."""
    import uuid
    session_id = f"chat_{uuid.uuid4().hex[:12]}"
    _sessions[session_id] = []
    _save_session_history(session_id, [])
    return {"session_id": session_id, "status": "created"}
