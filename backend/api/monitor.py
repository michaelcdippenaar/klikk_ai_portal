"""
API endpoints for agent monitoring — proxies to Django backend.

GET /api/monitor/performance?hours=24&tool_name=...
GET /api/monitor/sessions?days=7
GET /api/monitor/health
GET /api/monitor/errors?hours=24&tool_name=...&limit=20
GET /api/monitor/slow-tools?hours=24&threshold_ms=2000&limit=20
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Request

from config import settings
from logger import log

router = APIRouter()

DJANGO_BASE = settings.auth_api_url.rstrip("/")  # e.g. http://192.168.1.235:8001


async def _proxy_get(request: Request, path: str) -> dict:
    """Forward a GET request to Django's AI Agent monitor endpoints."""
    url = f"{DJANGO_BASE}/api/ai-agent/monitor/{path}"
    # Forward query params and auth header
    headers = {}
    auth_header = request.headers.get("authorization")
    if auth_header:
        headers["Authorization"] = auth_header
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=dict(request.query_params), headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        log.warning("Monitor proxy %s returned %s", path, e.response.status_code)
        return {"error": f"Django returned {e.response.status_code}", "detail": e.response.text[:500]}
    except Exception as e:
        log.error("Monitor proxy error for %s: %s", path, e)
        return {"error": str(e)}


@router.get("/performance")
async def get_performance(request: Request):
    return await _proxy_get(request, "performance/")


@router.get("/sessions")
async def get_sessions(request: Request):
    return await _proxy_get(request, "sessions/")


@router.get("/health")
async def get_health(request: Request):
    return await _proxy_get(request, "health/")


@router.get("/errors")
async def get_errors(request: Request):
    return await _proxy_get(request, "errors/")


@router.get("/slow-tools")
async def get_slow_tools(request: Request):
    return await _proxy_get(request, "slow-tools/")


@router.get("/live")
async def get_live(request: Request):
    return await _proxy_get(request, "live/")
