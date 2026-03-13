"""
Authentication middleware and dependencies for the Klikk AI Portal.

Validates JWT tokens by proxy-verifying against Klikk Financials V4 (Django).
Includes a 5-minute verification cache to avoid hitting Django on every request.
"""
from __future__ import annotations

import time
import threading
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from logger import log
from tm1_session import get_tm1_auth

# ---------------------------------------------------------------------------
# Token verification cache — {token: (user_dict, expires_at)}
# ---------------------------------------------------------------------------
_token_cache: dict[str, tuple[dict, float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes


def _cache_get(token: str) -> Optional[dict]:
    """Return cached user dict if token is still valid, else None."""
    with _cache_lock:
        entry = _token_cache.get(token)
        if entry and entry[1] > time.time():
            return entry[0]
        # Expired — remove
        _token_cache.pop(token, None)
    return None


def _cache_set(token: str, user: dict) -> None:
    """Cache a verified token for _CACHE_TTL seconds."""
    with _cache_lock:
        _token_cache[token] = (user, time.time() + _CACHE_TTL)
        # Evict old entries periodically (keep cache bounded)
        if len(_token_cache) > 500:
            now = time.time()
            expired = [k for k, (_, exp) in _token_cache.items() if exp <= now]
            for k in expired:
                del _token_cache[k]


def _cache_remove(token: str) -> None:
    """Remove a token from cache (e.g. on logout)."""
    with _cache_lock:
        _token_cache.pop(token, None)


# ---------------------------------------------------------------------------
# Token verification against Klikk Financials V4
# ---------------------------------------------------------------------------

async def verify_token(token: str) -> Optional[dict]:
    """
    Verify a JWT access token by calling the Klikk Financials V4 verify
    endpoint.  Returns the user dict on success, None on failure.
    """
    # Check cache first
    cached = _cache_get(token)
    if cached is not None:
        return cached

    from config import settings

    verify_url = f"{settings.auth_api_url}/api/auth/token/verify/"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(verify_url, json={"token": token})

        if resp.status_code != 200:
            log.debug("Token verification failed: HTTP %s", resp.status_code)
            return None

        # Token is valid — try to extract user info from the response
        # Django Simple JWT verify returns {} on success, so we decode
        # user info from the token payload (JWT is base64-encoded JSON)
        user = _decode_jwt_payload(token)
        if user:
            _cache_set(token, user)
        return user

    except httpx.ConnectError:
        log.warning("Cannot reach auth API at %s for token verification", settings.auth_api_url)
        return None
    except Exception as e:
        log.error("Token verification error: %s", e, exc_info=True)
        return None


def _decode_jwt_payload(token: str) -> Optional[dict]:
    """Decode the payload section of a JWT (without cryptographic verification)."""
    import base64
    import json as json_mod

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Add padding
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json_mod.loads(base64.urlsafe_b64decode(payload_b64))
        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("username", ""),
            "email": payload.get("email", ""),
            "exp": payload.get("exp"),
            "token_type": payload.get("token_type", ""),
        }
    except Exception:
        return {"user_id": None, "username": "unknown"}


# ---------------------------------------------------------------------------
# FastAPI dependency — require_auth
# ---------------------------------------------------------------------------

security = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI dependency that validates JWT and returns user info.
    Use: user = Depends(require_auth)
    """
    from config import settings

    # Bypass auth entirely when disabled (development mode)
    if not settings.auth_required:
        return {"user_id": 0, "username": "dev", "email": "dev@localhost"}

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await verify_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


# ---------------------------------------------------------------------------
# WebSocket token verification helper
# ---------------------------------------------------------------------------

async def verify_ws_token(token: str | None) -> Optional[dict]:
    """
    Verify a token provided via WebSocket query parameter.
    Returns user dict on success, None on failure.
    When auth is disabled, returns a dev user.
    """
    from config import settings

    if not settings.auth_required:
        return {"user_id": 0, "username": "dev", "email": "dev@localhost"}

    if not token:
        return None

    return await verify_token(token)
