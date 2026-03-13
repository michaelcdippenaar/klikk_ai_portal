"""
Authentication — login via Klikk Financials V4 JWT + TM1 session.

Flow:
1. User POSTs username/password to /api/auth/login
2. Backend authenticates against Klikk Financials V4 (Django JWT)
3. Backend also creates a TM1 REST session
4. Returns JWT access/refresh tokens to the browser
5. Every subsequent API call must include Authorization: Bearer <access_token>
6. TM1 session token is stored server-side, keyed by user
"""
from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth_middleware import require_auth, _cache_remove
from config import settings
from logger import log
from tm1_session import (
    clear_tm1_session,
    get_tm1_auth,
    has_tm1_session,
    store_tm1_session,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str
    tm1_user: Optional[str] = None
    tm1_password: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _klikk_login(username: str, password: str) -> dict:
    """Authenticate against Klikk Financials V4 Django JWT endpoint."""
    url = f"{settings.auth_api_url}/api/auth/login/"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={
                "username": username,
                "password": password,
            })
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code in (400, 401):
            detail = "Invalid username or password"
            try:
                body = resp.json()
                detail = body.get("detail", detail)
            except Exception:
                pass
            return {"error": detail, "status_code": resp.status_code}
        else:
            return {"error": f"Auth API returned HTTP {resp.status_code}", "status_code": resp.status_code}
    except httpx.ConnectError:
        log.error("Cannot reach Klikk Financials V4 auth API at %s", settings.auth_api_url)
        return {"error": "Authentication service is unreachable. Please try again later."}
    except Exception as e:
        log.error("Klikk auth error: %s", e, exc_info=True)
        return {"error": f"Authentication error: {str(e)}"}


async def _klikk_refresh(refresh_token: str) -> dict:
    """Refresh access token via Klikk Financials V4."""
    url = f"{settings.auth_api_url}/api/auth/refresh/"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"refresh": refresh_token})
        if resp.status_code == 200:
            return resp.json()
        else:
            detail = "Token refresh failed"
            try:
                body = resp.json()
                detail = body.get("detail", detail)
            except Exception:
                pass
            return {"error": detail, "status_code": resp.status_code}
    except httpx.ConnectError:
        log.error("Cannot reach auth API for token refresh")
        return {"error": "Authentication service is unreachable."}
    except Exception as e:
        log.error("Token refresh error: %s", e, exc_info=True)
        return {"error": f"Refresh error: {str(e)}"}


async def _create_tm1_session(tm1_user: str, tm1_password: str) -> dict:
    """Verify TM1 credentials via GET /api/v1/ActiveSession with Basic auth."""
    tm1_base = f"http://{settings.tm1_host}:{settings.tm1_port}/api/v1"
    url = f"{tm1_base}/ActiveSession"
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(
                url,
                auth=(tm1_user, tm1_password),
                headers={"Accept": "application/json"},
            )
        if resp.status_code in (200, 201):
            cookies = dict(resp.cookies)
            return {"ok": True, "cookies": cookies, "session": resp.json() if resp.text else {}}
        else:
            detail = resp.text[:200]
            log.warning("TM1 session creation failed: HTTP %s — %s", resp.status_code, detail)
            return {"ok": False, "error": f"HTTP {resp.status_code}: {detail}"}
    except httpx.ConnectError:
        log.warning("Cannot reach TM1 server at %s for session creation", tm1_base)
        return {"ok": False, "error": "TM1 server is unreachable"}
    except Exception as e:
        log.error("TM1 session creation error: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(body: LoginRequest):
    """
    Authenticate user against Klikk Financials V4 and optionally create
    a TM1 REST session.

    Returns JWT tokens (access + refresh) and TM1 auth status.
    """
    # Step 1: Authenticate with Klikk Financials V4
    klikk_result = await _klikk_login(body.username, body.password)

    if "error" in klikk_result:
        status_code = klikk_result.get("status_code", 401)
        raise HTTPException(status_code=status_code, detail=klikk_result["error"])

    tokens = klikk_result.get("tokens", {})
    user_info = klikk_result.get("user", {})

    if not tokens.get("access"):
        raise HTTPException(status_code=502, detail="Auth API did not return tokens")

    log.info("User '%s' authenticated via Klikk Financials V4", body.username)

    # Step 2: Create TM1 session (optional — use defaults if not provided)
    tm1_user = body.tm1_user or settings.tm1_user
    tm1_password = body.tm1_password if body.tm1_password is not None else settings.tm1_password
    tm1_authenticated = False

    tm1_result = await _create_tm1_session(tm1_user, tm1_password)
    tm1_error = ""
    if tm1_result.get("ok"):
        store_tm1_session(
            username=body.username,
            tm1_user=tm1_user,
            tm1_password=tm1_password,
            cookies=tm1_result.get("cookies", {}),
        )
        tm1_authenticated = True
        log.info("TM1 session created for user '%s' (tm1_user=%s)", body.username, tm1_user)
    else:
        tm1_error = tm1_result.get("error", "TM1 connection failed")
        log.warning("TM1 session creation failed for '%s': %s", body.username, tm1_error)

    return {
        "user": user_info,
        "tokens": tokens,
        "tm1_authenticated": tm1_authenticated,
        "tm1_error": tm1_error if not tm1_authenticated else "",
    }


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    """Refresh the JWT access token via Klikk Financials V4."""
    result = await _klikk_refresh(body.refresh)

    if "error" in result:
        status_code = result.get("status_code", 401)
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result


@router.post("/logout")
async def logout(request: Request, user: dict = Depends(require_auth)):
    """Clear server-side TM1 session and invalidate cached token."""
    username = user.get("username", "")

    # Clear TM1 session
    clear_tm1_session(username)

    # Remove token from verification cache
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        _cache_remove(token)

    log.info("User '%s' logged out", username)
    return {"status": "logged_out", "username": username}


@router.get("/me")
async def me(user: dict = Depends(require_auth)):
    """Return current user info from the JWT token."""
    return {"user": user}


@router.get("/status")
async def status(user: dict = Depends(require_auth)):
    """Return auth status for both Klikk Financials and TM1."""
    username = user.get("username", "")
    tm1_connected = has_tm1_session(username)

    return {
        "authenticated": True,
        "username": username,
        "user_id": user.get("user_id"),
        "klikk_financials": True,
        "tm1_connected": tm1_connected,
    }
