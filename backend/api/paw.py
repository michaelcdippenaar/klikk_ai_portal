"""
PAW (Planning Analytics Workspace) proxy -- handles authentication and
embeds PAW views/books/editors into the Klikk AI Portal.

Uses the official IBM PAW UI API: https://ibm.github.io/planninganalyticsapi/

Authentication:  POST {paw_base}/login  (TM1 native mode 1)
Embed URL:       GET  {paw_base}/ui?type=<widget_type>&server=...&cube=...
AJAX requests:   GET  {paw_base}/api/v0/tm1/{server}/api/v1/...

The proxy:
1. Authenticates once with PAW/TM1 using TM1 native credentials
2. Proxies API calls for discovering books, views, subsets
3. Generates iframe embed URLs per the official PAW UI API spec

PAW Local iframe embedding: You must enable CORS (Cross-Origin Resource Sharing)
in the Planning Analytics Workspace configuration so the parent site can
communicate with the PAW domain. See documentation/PAW_EMBED.md.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from logger import log

router = APIRouter()

# ---------------------------------------------------------------------------
#  PAW session management (singleton, thread-safe)
# ---------------------------------------------------------------------------

_session_lock = threading.Lock()
_paw_session: requests.Session | None = None
_paw_server_name: str = ""


def _paw_base_url() -> str:
    return f"http://{settings.paw_host}:{settings.paw_port}"


def _tm1_api_base() -> str:
    return f"http://{settings.tm1_host}:{settings.tm1_port}/api/v1"


def _get_paw_session(force_refresh: bool = False) -> requests.Session:
    """
    Get or create an authenticated PAW/TM1 session.
    Uses TM1 native auth via basic auth to the TM1 REST API.
    """
    global _paw_session, _paw_server_name

    with _session_lock:
        if _paw_session is not None and not force_refresh:
            return _paw_session

        log.info("PAW: Authenticating to TM1 at %s:%s", settings.tm1_host, settings.tm1_port)
        sess = requests.Session()
        sess.verify = False
        sess.headers.update({"Accept": "application/json"})

        try:
            resp = sess.get(
                f"{_tm1_api_base()}/ActiveSession",
                auth=(settings.tm1_user, settings.tm1_password),
                timeout=10,
            )
            resp.raise_for_status()
            log.info("PAW: TM1 authentication successful")
        except requests.RequestException as e:
            log.error("PAW: TM1 authentication failed: %s", e)
            raise ConnectionError(f"TM1 authentication failed: {e}") from e

        # Auto-detect server name if not configured
        if not _paw_server_name:
            _paw_server_name = settings.paw_server_name
            if not _paw_server_name:
                try:
                    info_resp = sess.get(
                        f"{_tm1_api_base()}/Configuration",
                        timeout=10,
                    )
                    if info_resp.ok:
                        config_data = info_resp.json()
                        _paw_server_name = config_data.get("ServerName", "")
                        log.info("PAW: Auto-detected TM1 server name: %s", _paw_server_name)
                except Exception as e:
                    log.warning("PAW: Could not auto-detect server name: %s", e)

        _paw_session = sess
        return _paw_session


def _safe_paw_call(func) -> dict[str, Any]:
    """Wrap a PAW API call with error handling and session retry."""
    if not settings.paw_enabled:
        return {"error": "PAW integration is disabled. Set PAW_ENABLED=true in .env"}
    try:
        return func()
    except ConnectionError as e:
        return {"error": str(e)}
    except requests.RequestException as e:
        # Retry once with fresh session
        log.warning("PAW: Request failed, retrying with fresh session: %s", e)
        try:
            _get_paw_session(force_refresh=True)
            return func()
        except Exception as retry_e:
            return {"error": f"PAW request failed after retry: {retry_e}"}
    except Exception as e:
        return {"error": f"PAW error: {e}"}


# ---------------------------------------------------------------------------
#  API endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def paw_status():
    """Check PAW connectivity and version."""
    def _check():
        sess = _get_paw_session()
        result = {
            "paw_url": _paw_base_url(),
            "tm1_api": _tm1_api_base(),
            "server_name": _paw_server_name,
            "connected": True,
        }
        # Try to get PAW version info
        try:
            resp = sess.get(f"{_paw_base_url()}/api/v0/info", timeout=5)
            if resp.ok:
                result["paw_info"] = resp.json()
        except Exception:
            result["paw_info"] = None
        # Verify TM1 session is alive
        try:
            resp = sess.get(f"{_tm1_api_base()}/ActiveSession", timeout=5)
            result["tm1_session_active"] = resp.ok
        except Exception:
            result["tm1_session_active"] = False
        return result

    return _safe_paw_call(_check)


@router.get("/books")
async def paw_list_books():
    """List available PAW books/sheets."""
    def _list():
        sess = _get_paw_session()
        # PAW 2.0 books API
        resp = sess.get(f"{_paw_base_url()}/api/v0/Books", timeout=10)
        if resp.ok:
            books = resp.json()
            if isinstance(books, dict) and "value" in books:
                books = books["value"]
            return {
                "books": [
                    {
                        "id": b.get("ID", b.get("id", "")),
                        "name": b.get("Name", b.get("name", "")),
                        "description": b.get("Description", b.get("description", "")),
                    }
                    for b in (books if isinstance(books, list) else [])
                ],
                "count": len(books) if isinstance(books, list) else 0,
            }
        return {"books": [], "count": 0, "note": f"PAW books API returned {resp.status_code}"}

    return _safe_paw_call(_list)


@router.get("/views/{cube_name}")
async def paw_list_views(cube_name: str):
    """List saved views for a cube."""
    def _list():
        sess = _get_paw_session()
        resp = sess.get(
            f"{_tm1_api_base()}/Cubes('{cube_name}')/Views",
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            views = data.get("value", [])
            return {
                "cube": cube_name,
                "views": [
                    {
                        "name": v.get("Name", ""),
                        "type": "private" if v.get("@odata.type", "").endswith("PrivateView") else "public",
                    }
                    for v in views
                ],
                "count": len(views),
            }
        return {"cube": cube_name, "views": [], "count": 0, "note": f"TM1 API returned {resp.status_code}"}

    return _safe_paw_call(_list)


@router.get("/subsets/{dimension_name}")
async def paw_list_subsets(dimension_name: str):
    """List saved subsets for a dimension."""
    def _list():
        sess = _get_paw_session()
        resp = sess.get(
            f"{_tm1_api_base()}/Dimensions('{dimension_name}')/Hierarchies('{dimension_name}')/Subsets",
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            subsets = data.get("value", [])
            return {
                "dimension": dimension_name,
                "subsets": [
                    {
                        "name": s.get("Name", ""),
                        "type": "dynamic" if s.get("Expression") else "static",
                        "element_count": len(s.get("Elements", [])),
                    }
                    for s in subsets
                ],
                "count": len(subsets),
            }
        return {"dimension": dimension_name, "subsets": [], "count": 0, "note": f"TM1 API returned {resp.status_code}"}

    return _safe_paw_call(_list)


class EmbedRequest(BaseModel):
    type: str  # "cube_viewer" | "dimension_editor" | "book"
    target: str  # cube name, dimension name, or book ID
    params: dict = {}


@router.post("/embed")
async def paw_generate_embed(req: EmbedRequest):
    """
    Generate an embed URL for a PAW component using the official PAW UI API.
    URL format: {paw_base}/ui?type=<widget_type>&server=<server>&...
    Reference: https://ibm.github.io/planninganalyticsapi/
    """
    if not settings.paw_enabled:
        return {"error": "PAW integration is disabled. Set PAW_ENABLED=true in .env"}

    import urllib.parse

    # Route through /paw/ reverse proxy to keep iframe same-origin,
    # avoiding CORS and CSP frame-ancestors issues with PAW Local.
    server = _paw_server_name or settings.paw_server_name or "default"

    if req.type == "cube_viewer":
        query_params: dict[str, str] = {
            "type": "cube-viewer",
            "server": server,
            "cube": req.target,
        }
        if req.params.get("view"):
            query_params["view"] = req.params["view"]
        if req.params.get("private"):
            query_params["private"] = "true"
        if req.params.get("toolbar"):
            query_params["toolbar"] = req.params["toolbar"]
        url = f"/paw/ui?{urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)}"

    elif req.type == "dimension_editor":
        query_params = {
            "type": "dimension-editor",
            "server": server,
            "dimension": req.target,
        }
        if req.params.get("hierarchy"):
            query_params["hierarchy"] = req.params["hierarchy"]
        url = f"/paw/ui?{urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)}"

    elif req.type == "set_editor":
        if not req.params.get("cube"):
            raise HTTPException(status_code=400, detail="set_editor requires 'cube' in params")
        if not req.params.get("uniqueName"):
            raise HTTPException(status_code=400, detail="set_editor requires 'uniqueName' in params")
        query_params = {
            "type": "set-editor",
            "server": server,
            "cube": req.params["cube"],
            "dimension": req.target,
            "uniqueName": req.params["uniqueName"],
        }
        if req.params.get("hierarchy"):
            query_params["hierarchy"] = req.params["hierarchy"]
        if req.params.get("alias"):
            query_params["alias"] = req.params["alias"]
        if req.params.get("private"):
            query_params["private"] = "true"
        url = f"/paw/ui?{urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)}"

    elif req.type == "book":
        if req.params.get("embed", True):
            query_params = {
                "perspective": "dashboard",
                "path": req.target,
                "embed": "true",
            }
            url = f"/paw/?{urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)}"
        else:
            query_params = {"type": "book", "path": req.target}
            url = f"/paw/ui?{urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)}"

    elif req.type == "websheet":
        query_params = {
            "type": "websheet",
            "TM1Server": server,
            "AdminHost": req.params.get("AdminHost", "localhost"),
            "Action": req.params.get("Action", "Open"),
        }
        if req.params.get("Workbook"):
            query_params["Workbook"] = req.params["Workbook"]
        url = f"/paw/ui?{urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)}"

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid embed type: {req.type}. "
                   f"Use: cube_viewer, dimension_editor, set_editor, book, websheet"
        )

    return {
        "embed_url": url,
        "type": req.type,
        "target": req.target,
        "server_name": server,
    }


@router.get("/session")
async def paw_session():
    """Get/refresh the PAW session token for the backend."""
    def _refresh():
        sess = _get_paw_session(force_refresh=True)
        return {
            "status": "authenticated",
            "server_name": _paw_server_name,
            "tm1_api": _tm1_api_base(),
            "paw_url": _paw_base_url(),
        }

    return _safe_paw_call(_refresh)


@router.get("/auth-url")
async def paw_auth_url():
    """
    Return PAW proxy login URL and credentials for frontend iframe auth.
    Frontend should POST to /paw/login (proxied same-origin) with JSON body.
    """
    if not settings.paw_enabled:
        return {"error": "PAW integration is disabled"}

    return {
        "paw_base": "/paw",
        "login_endpoint": "/paw/login",
        "username": settings.tm1_user,
        "password": settings.tm1_password,
        "server_name": _paw_server_name or settings.paw_server_name,
    }


@router.get("/inspect")
async def paw_inspect(url: str = ""):
    """
    Debug endpoint: fetch a PAW URL from the backend and return the response
    headers + first 5KB of HTML. Useful for diagnosing blank widget issues.
    Usage: /api/paw/inspect?url=/paw/ui?type=cube-viewer&server=X&cube=Y
    """
    if not settings.paw_enabled:
        return {"error": "PAW integration is disabled"}

    target = url or f"{_paw_base_url()}/ui"
    if target.startswith("/paw"):
        target = _paw_base_url() + target[4:]

    try:
        sess = _get_paw_session()
        resp = sess.get(target, timeout=10, allow_redirects=True)
        return {
            "url": target,
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "html_preview": resp.text[:5000],
            "content_length": len(resp.text),
            "cookies": {k: v for k, v in resp.cookies.items()},
        }
    except Exception as e:
        return {"error": str(e), "url": target}


# ---------------------------------------------------------------------------
#  Query state decode & saved views (recall view by queryState / MDX)
# ---------------------------------------------------------------------------

class DecodeQueryStateRequest(BaseModel):
    queryState: str  # Base64-encoded, Gzip-compressed JSON from PAW


@router.post("/decode-query-state")
async def paw_decode_query_state(req: DecodeQueryStateRequest):
    """
    Decode PAW queryState (Base64 + Gzip JSON) to raw JSON.
    The result contains MDX-generating instructions, hierarchy sets, member selections.
    Use this to inspect view structure or derive MDX for extraction.
    """
    try:
        from agent_view_store import decode_query_state_to_json
        decoded = decode_query_state_to_json(req.queryState)
        return {"decoded": decoded, "keys": list(decoded.keys()) if isinstance(decoded, dict) else []}
    except Exception as e:
        log.warning("decode-query-state failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid queryState: {e}") from e


_SAVED_VIEWS_FILE = Path(__file__).resolve().parent.parent.parent / "logs" / "saved_views.json"


def _load_saved_views() -> list[dict]:
    if not _SAVED_VIEWS_FILE.exists():
        return []
    try:
        with open(_SAVED_VIEWS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("views", [])
    except Exception:
        return []


def _save_views_list(views: list[dict]) -> None:
    _SAVED_VIEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SAVED_VIEWS_FILE, "w", encoding="utf-8") as f:
        json.dump({"views": views}, f, indent=2)


class SaveViewRequest(BaseModel):
    cubeName: str
    serverName: str
    queryState: str
    mdx: str | None = None  # optional: extracted MDX for this view
    label: str | None = None


@router.get("/saved-views")
async def list_saved_views():
    """List saved PAW views (queryState + optional MDX) for recall."""
    views = _load_saved_views()
    return {"views": views, "count": len(views)}


@router.post("/saved-views")
async def save_view(req: SaveViewRequest):
    """Save a view (cubeName, serverName, queryState, optional mdx/label) for later recall."""
    import uuid
    views = _load_saved_views()
    view_id = f"v_{uuid.uuid4().hex[:8]}"
    entry = {
        "id": view_id,
        "cubeName": req.cubeName,
        "serverName": req.serverName,
        "queryState": req.queryState,
        "mdx": req.mdx,
        "label": req.label or f"{req.cubeName}",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    views.append(entry)
    _save_views_list(views)
    return {"status": "saved", "view": entry}


@router.get("/saved-views/{view_id}")
async def get_saved_view(view_id: str):
    """Get one saved view by id (for recall). Includes recall_url (path under /paw) for iframe."""
    import urllib.parse
    for v in _load_saved_views():
        if v.get("id") == view_id:
            qs = urllib.parse.urlencode({
                "queryState": v["queryState"],
                "serverName": v["serverName"],
            })
            v = dict(v)
            # Path under portal so iframe loads via /paw proxy (same-origin)
            v["recall_url"] = f"/paw/api/v1/viewer/view?{qs}"
            return v
    raise HTTPException(status_code=404, detail="View not found")


@router.delete("/saved-views/{view_id}")
async def delete_saved_view(view_id: str):
    views = [v for v in _load_saved_views() if v.get("id") != view_id]
    _save_views_list(views)
    return {"status": "deleted", "view_id": view_id}


# ---------------------------------------------------------------------------
#  PAW proxy logs — recent PAW-related entries from portal.log
# ---------------------------------------------------------------------------

_PORTAL_LOG_FILE = Path(__file__).resolve().parent.parent.parent / "logs" / "portal.log"


@router.get("/logs")
async def paw_logs(limit: int = 100):
    """Return recent PAW-related log entries for the diagnostics page."""
    if not _PORTAL_LOG_FILE.exists():
        return {"entries": [], "note": "Log file not found"}

    entries: list[dict] = []
    try:
        with open(_PORTAL_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Scan from end, collect PAW-related lines
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if "paw" not in lower and "proxy" not in lower:
                continue
            try:
                entry = json.loads(line)
                entries.append({
                    "ts": entry.get("ts", ""),
                    "level": entry.get("level", ""),
                    "module": entry.get("module", ""),
                    "message": entry.get("message", ""),
                })
            except (json.JSONDecodeError, KeyError):
                entries.append({"ts": "", "level": "RAW", "module": "", "message": line[:500]})
            if len(entries) >= limit:
                break
    except Exception as e:
        return {"entries": [], "error": str(e)}

    entries.reverse()  # chronological order
    return {"entries": entries, "count": len(entries)}
