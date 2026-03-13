"""
Log viewer API — exposes structured error logs and chat session transcripts.
Reads from the JSON log files in logs/ directory.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

router = APIRouter()

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "errors.log"
CHAT_LOG_DIR = LOG_DIR / "chat_sessions"
JS_LOG_FILE = LOG_DIR / "frontend.log"


def _read_log_lines() -> list[dict]:
    """Read all JSON lines from the error log file."""
    if not LOG_FILE.exists():
        return []

    entries: list[dict] = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _filter_entries(
    entries: list[dict],
    tool: Optional[str] = None,
    since: Optional[str] = None,
) -> list[dict]:
    """Apply optional filters to log entries."""
    if tool:
        entries = [e for e in entries if e.get("tool", "") == tool]

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            entries = [
                e for e in entries
                if _parse_ts(e.get("ts", "")) is not None
                and _parse_ts(e.get("ts", "")) >= since_dt  # type: ignore[operator]
            ]
        except (ValueError, TypeError):
            pass

    return entries


def _parse_ts(ts_str: str) -> Optional[datetime]:
    """Safely parse an ISO timestamp string."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


@router.get("/errors")
async def get_errors(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tool: Optional[str] = Query(None, description="Filter by tool name"),
    since: Optional[str] = Query(None, description="ISO datetime — return errors after this time"),
):
    """Return recent errors with optional filtering."""
    entries = _read_log_lines()
    entries = _filter_entries(entries, tool=tool, since=since)

    # Most recent first
    entries.reverse()

    total = len(entries)
    page = entries[offset : offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "errors": page,
    }


@router.get("/errors/stats")
async def get_error_stats():
    """Aggregated error stats: counts by tool, error_type, and hour."""
    entries = _read_log_lines()

    by_tool: dict[str, int] = defaultdict(int)
    by_error_type: dict[str, int] = defaultdict(int)
    by_hour: dict[str, int] = defaultdict(int)

    for e in entries:
        tool = e.get("tool", "unknown")
        error_type = e.get("error_type", "unknown")
        ts = _parse_ts(e.get("ts", ""))

        by_tool[tool] += 1
        by_error_type[error_type] += 1

        if ts:
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            by_hour[hour_key] += 1

    return {
        "total": len(entries),
        "by_tool": dict(by_tool),
        "by_error_type": dict(by_error_type),
        "by_hour": dict(by_hour),
    }


@router.get("/errors/search")
async def search_errors(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(50, ge=1, le=500),
):
    """Search errors by keyword in message/detail fields."""
    entries = _read_log_lines()
    q_lower = q.lower()

    matches = [
        e for e in entries
        if q_lower in e.get("message", "").lower()
        or q_lower in e.get("detail", "").lower()
        or q_lower in e.get("exception", "").lower()
    ]

    # Most recent first
    matches.reverse()

    return {
        "query": q,
        "total": len(matches),
        "errors": matches[:limit],
    }


# ---------------------------------------------------------------------------
#  Chat session logs
# ---------------------------------------------------------------------------

def _parse_session_file(path: Path) -> dict:
    """Extract metadata from a session log file's header."""
    info: dict = {
        "session_id": path.stem,
        "file": path.name,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "modified": datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            head = f.read(512)
        for line in head.splitlines():
            if line.startswith("Started:"):
                info["started"] = line.split(":", 1)[1].strip()
            elif line.startswith("User:"):
                info["user"] = line.split(":", 1)[1].strip()
        info["turns"] = head.count("Turn ")
    except Exception:
        pass
    return info


def _count_turns(path: Path) -> int:
    """Count turns in a session file by counting separator lines."""
    try:
        text = path.read_text(encoding="utf-8")
        return text.count("\nUSER:\n")
    except Exception:
        return 0


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
):
    """List all chat session log files, most recent first."""
    if not CHAT_LOG_DIR.is_dir():
        return {"sessions": [], "count": 0}

    files = sorted(CHAT_LOG_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    sessions = []
    for f in files[:limit]:
        info = _parse_session_file(f)
        info["turns"] = _count_turns(f)
        sessions.append(info)

    return {"sessions": sessions, "count": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_session_log(session_id: str):
    """Return the full text of a session log."""
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    path = CHAT_LOG_DIR / f"{safe_id}.txt"

    if not path.exists():
        return {"error": f"Session '{session_id}' not found"}

    return PlainTextResponse(
        path.read_text(encoding="utf-8"),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/sessions/{session_id}/review")
async def review_session(session_id: str):
    """
    Analyse a session log and return structured insights:
    - tools used (frequency, errors)
    - widgets created
    - patterns / areas for skill improvement
    """
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    path = CHAT_LOG_DIR / f"{safe_id}.txt"

    if not path.exists():
        return {"error": f"Session '{session_id}' not found"}

    text = path.read_text(encoding="utf-8")

    # --- Parse turns ---
    turns = text.split("=" * 72)
    turn_count = 0
    tool_usage: dict[str, int] = defaultdict(int)
    tool_errors: dict[str, list[str]] = defaultdict(list)
    widgets_created: list[dict] = []
    user_questions: list[str] = []
    errors: list[str] = []

    for block in turns:
        if "USER:" not in block:
            continue
        turn_count += 1

        # Extract user question
        user_match = re.search(r"USER:\n(.+?)(?:\n\n|\nTOOL|\nASSISTANT)", block, re.DOTALL)
        if user_match:
            user_questions.append(user_match.group(1).strip()[:200])

        # Extract tool calls
        for tc_match in re.finditer(r"> (\w+)\(", block):
            tool_name = tc_match.group(1)
            tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1

        # Detect tool errors in results
        for err_match in re.finditer(r'> (\w+)\(.*?\n\s+Result:.*?"error":\s*"([^"]+)"', block, re.DOTALL):
            tool_errors[err_match.group(1)].append(err_match.group(2)[:150])

        # Widgets
        for w_match in re.finditer(r"- (\w+): (.+?) \(id=", block):
            widgets_created.append({"type": w_match.group(1), "title": w_match.group(2)})

        # Errors
        err_block = re.search(r"ERROR:\n(.+?)(?:\n\n|\nASSISTANT)", block, re.DOTALL)
        if err_block:
            errors.append(err_block.group(1).strip()[:200])

    # --- Build improvement suggestions ---
    suggestions: list[str] = []

    failed_tools = {t for t, errs in tool_errors.items() if len(errs) > 0}
    if failed_tools:
        suggestions.append(
            f"Tools with errors: {', '.join(sorted(failed_tools))}. "
            "Review error patterns and add better input validation or fallback logic."
        )

    unused_common = {"tm1_validate_elements", "tm1_find_element"} - set(tool_usage.keys())
    if unused_common and any("not found" in e.lower() or "member" in e.lower() for e in errors):
        suggestions.append(
            "Element-not-found errors occurred but tm1_validate_elements / tm1_find_element "
            "were not used. Consider prompting the model to validate elements first."
        )

    if tool_usage.get("tm1_get_dimension_elements", 0) > 3:
        suggestions.append(
            "tm1_get_dimension_elements called many times. Consider caching dimension "
            "element lists in the system prompt or element_context store."
        )

    if not widgets_created and turn_count > 3:
        suggestions.append(
            "No widgets were created in this session. If the user asked for data "
            "visualisation, the agent may need stronger prompting to use create_dashboard_widget."
        )

    if errors:
        suggestions.append(
            f"{len(errors)} error(s) occurred. Review error logs and add "
            "retry logic or better error messages for the affected tools."
        )

    top_tools = sorted(tool_usage.items(), key=lambda x: -x[1])[:10]

    return {
        "session_id": session_id,
        "turns": turn_count,
        "user_questions": user_questions,
        "tool_usage": dict(top_tools),
        "tool_errors": {t: errs[:5] for t, errs in tool_errors.items()},
        "widgets_created": widgets_created,
        "errors": errors,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
#  Frontend JavaScript log sink
# ---------------------------------------------------------------------------

class JSLogEntry(BaseModel):
    level: str = "info"       # info, warn, error, debug
    message: str
    source: str = "frontend"  # component/module name
    data: dict | None = None


class JSLogBatch(BaseModel):
    entries: list[JSLogEntry]


def _append_js_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(JS_LOG_FILE, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


@router.post("/js")
async def receive_js_logs(batch: JSLogBatch):
    """Receive frontend JS log entries and append to logs/frontend.log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    for e in batch.entries:
        extra = json.dumps(e.data, default=str) if e.data else ""
        lines.append(f"[{ts}] [{e.level.upper():5s}] [{e.source}] {e.message}{' | ' + extra if extra else ''}")
    _append_js_log(lines)
    return {"status": "ok", "count": len(lines)}


@router.get("/js")
async def get_js_logs(
    tail: int = Query(200, ge=1, le=5000),
    level: str | None = Query(None, description="Filter by level: info, warn, error, debug"),
):
    """Return recent frontend JS log entries."""
    if not JS_LOG_FILE.exists():
        return {"lines": [], "count": 0}
    with open(JS_LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    if level:
        level_tag = f"[{level.upper()}"
        all_lines = [l for l in all_lines if level_tag in l]
    recent = all_lines[-tail:]
    return {"lines": [l.rstrip() for l in recent], "count": len(recent)}


@router.delete("/js")
async def clear_js_logs():
    """Clear the frontend JS log file."""
    if JS_LOG_FILE.exists():
        JS_LOG_FILE.unlink()
    return {"status": "cleared"}
