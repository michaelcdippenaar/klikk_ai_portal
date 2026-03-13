"""
Agent "local DB" for the PAW view currently in use.

When the user has a PAW widget open, the frontend sends cubeName, serverName,
and queryState with each message. We persist the latest as the "current view"
so the agent can:
- See what view the user is looking at (get_current_view)
- Decode queryState to get view structure or MDX (get_view_mdx)
- Execute MDX to get cell data (get_view_data)

Storage: single JSON file logs/agent_current_view.json
"""
from __future__ import annotations

import base64
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parent
_VIEW_FILE = _BACKEND_DIR.parent / "logs" / "agent_current_view.json"


def load_agent_current_view() -> dict[str, Any] | None:
    """Load the current PAW view stored for the agent (cubeName, serverName, queryState)."""
    if not _VIEW_FILE.exists():
        return None
    try:
        with open(_VIEW_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("queryState") and data.get("cubeName") and data.get("serverName"):
                return data
    except Exception:
        pass
    return None


def save_agent_current_view(cube_name: str, server_name: str, query_state: str) -> None:
    """Store the given view as the current one (overwrites)."""
    _VIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cubeName": cube_name,
        "serverName": server_name,
        "queryState": query_state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(_VIEW_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def decode_query_state_to_json(query_state: str) -> dict[str, Any]:
    """Decode PAW queryState (base64 + gzip JSON) to a Python dict. Raises on invalid input."""
    raw = base64.b64decode(query_state)
    decompressed = gzip.decompress(raw)
    return json.loads(decompressed.decode("utf-8"))
