"""
Klikk AI Portal — FastAPI Backend

Serves:
  - /api/*       REST + WebSocket endpoints
  - /*           Vue.js static frontend (from ./static/)

Run locally:
    cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import sys

# Ensure backend root is importable
sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from api.auth import router as auth_router
from api.chat import router as chat_router
from api.tm1 import router as tm1_router
from api.kpi import router as kpi_router
from api.widgets import router as widgets_router
from api.paw import router as paw_router
from api.logs import router as logs_router
from api.skills import router as skills_router
from api.context import router as context_router
from api.sql import router as sql_router
from logger import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    import asyncio
    from config import settings
    provider = settings.ai_provider.upper()
    model = settings.openai_model if provider == "OPENAI" else settings.anthropic_model
    log.info("Klikk AI Portal starting — AI: %s (%s)", provider, model,
             extra={"provider": provider, "model": model})
    log.info("TM1: %s:%s", settings.tm1_host, settings.tm1_port)
    log.info("PG:  %s:%s/%s", settings.pg_bi_host, settings.pg_bi_port, settings.pg_bi_db)

    # Ensure widget DB tables exist
    try:
        import widget_store
        widget_store.ensure_tables()
        # Migrate from YAML if DB is empty
        yaml_path = str(Path(__file__).parent / "widget_configs.yaml")
        migrated = widget_store.migrate_from_yaml(yaml_path)
        if migrated:
            log.info("Migrated %d widgets from YAML to DB", migrated)
    except Exception:
        log.warning("Widget store init failed (will retry on first access)", exc_info=True)

    # Start background refresh engine
    import refresh_engine
    _refresh_task = asyncio.create_task(refresh_engine.refresh_loop(interval=30))

    yield

    # Shutdown
    refresh_engine.stop()
    _refresh_task.cancel()
    log.info("Klikk AI Portal shutting down")


app = FastAPI(
    title="Klikk AI Portal",
    description="AI-powered TM1 Financial Planning Agent",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow local dev (Vite :5173) and PAW iframe origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(chat_router, prefix="/api")
app.include_router(tm1_router, prefix="/api/tm1")
app.include_router(kpi_router, prefix="/api/kpis")
app.include_router(widgets_router, prefix="/api/widgets")
app.include_router(paw_router, prefix="/api/paw")
app.include_router(logs_router, prefix="/api/logs")
app.include_router(skills_router, prefix="/api/skills")
app.include_router(context_router, prefix="/api/context")
app.include_router(sql_router, prefix="/api/sql")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "klikk-ai-portal"}


# ---------------------------------------------------------------------------
# Authentication middleware — checks Bearer token on all /api/* routes
# ---------------------------------------------------------------------------
# Paths that do NOT require authentication
_AUTH_WHITELIST = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/health",
}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Global auth middleware.  Skips non-API routes, whitelisted paths,
    OPTIONS preflight, and WebSocket upgrades (WS auth is handled in
    the chat endpoint via query-param token).
    """
    from config import settings

    path = request.url.path

    # Skip when auth is disabled (development mode)
    if not settings.auth_required:
        return await call_next(request)

    # Skip non-API routes, whitelisted endpoints, OPTIONS preflight, websocket
    # Also skip /api/v1/* — these are TM1 REST API calls from PAW's iframe JS
    if (
        not path.startswith("/api/")
        or path in _AUTH_WHITELIST
        or path.startswith("/api/v1/")
        or request.method == "OPTIONS"
        or "upgrade" in request.headers.get("connection", "").lower()
    ):
        return await call_next(request)

    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"},
        )

    token = auth_header.split(" ", 1)[1]

    from auth_middleware import verify_token
    user = await verify_token(token)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    # Attach user info to request state for downstream handlers
    request.state.user = user
    return await call_next(request)


# ---------------------------------------------------------------------------
# PAW reverse proxy — serves PAW under /paw/* so iframes are same-origin.
# In dev, Vite handles this; in production (Docker), FastAPI does.
# ---------------------------------------------------------------------------
import httpx
from fastapi.responses import StreamingResponse

import asyncio

_paw_client: httpx.AsyncClient | None = None
_paw_auth_lock = asyncio.Lock()


async def _get_paw_client() -> httpx.AsyncClient:
    """Get the PAW httpx client (no shared cookie jar — cookies managed per-browser)."""
    global _paw_client
    if _paw_client is None:
        from config import settings
        _paw_client = httpx.AsyncClient(
            base_url=f"http://{settings.paw_host}:{settings.paw_port}",
            timeout=30.0,
            verify=False,
            follow_redirects=False,
        )
    return _paw_client


async def _paw_login_for_browser() -> list[str]:
    """Perform form-login to PAW and return Set-Cookie headers for the browser.
    Uses /login/form/ (the general endpoint), NOT /login/tm1/.../form/.
    The general endpoint establishes the PAW web session (paSession + ba-sso-csrf)
    that the dashboard root page requires."""
    from config import settings
    client = await _get_paw_client()

    # Step 1: Visit login page to get initial paSession cookie
    login_resp = await client.get("/login")
    set_cookies: list[str] = []
    for k, v in login_resp.headers.multi_items():
        if k.lower() == "set-cookie":
            set_cookies.append(v)

    # Extract cookies from login page to send with form post
    page_cookies = {}
    for cookie in client.cookies.jar:
        page_cookies[cookie.name] = cookie.value

    # Step 2: POST to /login/form/ with credentials + mode=basic
    form_resp = await client.post(
        "/login/form/",
        data={"username": settings.tm1_user, "password": settings.tm1_password, "mode": "basic"},
        cookies=page_cookies,
    )

    if form_resp.status_code == 200 and "success = true" in form_resp.text:
        for k, v in form_resp.headers.multi_items():
            if k.lower() == "set-cookie":
                set_cookies.append(v)
        log.info("PAW browser-login succeeded (cookies: %s)",
                 [sc.split("=")[0] for sc in set_cookies])
    else:
        log.warning("PAW browser-login failed: %s", form_resp.status_code)

    # Clear client cookies — each browser manages its own session
    client.cookies.clear()
    return set_cookies


async def _proxy_to_paw(request: Request, path: str):
    """Forward a request to PAW, strip frame-blocking headers.
    Browser cookies are forwarded to PAW so each browser session is independent."""
    client = await _get_paw_client()
    url = f"/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    # Forward browser cookies to PAW (extract from browser request)
    browser_cookies: dict[str, str] = {}
    cookie_header = request.headers.get("cookie", "")
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                # Only forward PAW-related cookies
                if name.strip().startswith(("TM1SessionId", "paSession", "csrftoken")):
                    browser_cookies[name.strip()] = value.strip()

    log.info("PAW proxy: %s %s (browser cookies: %s)", request.method, url, list(browser_cookies.keys()))

    fwd_headers = {}
    skip = {"host", "connection", "transfer-encoding", "authorization", "cookie"}
    for key, value in request.headers.items():
        if key.lower() not in skip:
            fwd_headers[key] = value

    body = await request.body()

    resp = await client.request(
        method=request.method,
        url=url,
        headers=fwd_headers,
        content=body if body else None,
        cookies=browser_cookies,
    )

    # If PAW returns 401 (dashboard root page always does this without cookies),
    # auto-login and send Set-Cookie to browser + JS reload
    is_401_login = (
        resp.status_code == 401
        and "login" in resp.text[:500]
    )
    is_302_login = (
        resp.status_code in (301, 302, 303, 307)
        and "/login" in resp.headers.get("location", "")
    )
    if (is_401_login or is_302_login) and not browser_cookies:
        log.info("PAW proxy: no browser cookies, auto-logging in for %s", url)
        async with _paw_auth_lock:
            set_cookies = await _paw_login_for_browser()
        if set_cookies:
            # Return Set-Cookie + JS reload — browser will retry with cookies
            from starlette.responses import HTMLResponse
            reload_html = '<html><head><script>location.reload()</script></head></html>'
            response = HTMLResponse(reload_html, status_code=200)
            for sc in set_cookies:
                response.headers.append("set-cookie", sc)
            return response
    elif (is_401_login or is_302_login) and browser_cookies:
        # Browser has cookies but they expired — re-login and set new cookies
        log.info("PAW proxy: browser cookies expired, re-logging in for %s", url)
        async with _paw_auth_lock:
            set_cookies = await _paw_login_for_browser()
        if set_cookies:
            from starlette.responses import HTMLResponse
            reload_html = '<html><head><script>location.reload()</script></head></html>'
            response = HTMLResponse(reload_html, status_code=200)
            for sc in set_cookies:
                response.headers.append("set-cookie", sc)
            return response

    excluded = {
        "transfer-encoding", "connection", "content-encoding", "content-length",
        "x-frame-options", "content-security-policy",
        "access-control-allow-origin",
    }

    from config import settings as _cfg
    paw_origin = f"http://{_cfg.paw_host}:{_cfg.paw_port}"

    # Build single-value headers (skip set-cookie — handled separately for multi-value)
    resp_headers: dict[str, str] = {}
    set_cookie_headers: list[str] = []
    for k, v in resp.headers.multi_items():
        if k.lower() in excluded:
            continue
        if k.lower() == "set-cookie":
            set_cookie_headers.append(v)
            continue
        # Rewrite Location redirects to route through /paw/ proxy
        if k.lower() == "location":
            if v.startswith(paw_origin):
                v = "/paw" + v[len(paw_origin):]
            elif v.startswith("/") and not v.startswith("/paw"):
                v = "/paw" + v
        resp_headers[k] = v

    # Inject permissive CORS + frame policy for PAW widget iframes
    resp_headers["Access-Control-Allow-Origin"] = "*"
    resp_headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    resp_headers["Access-Control-Allow-Headers"] = "*"

    # Rewrite HTML/JS content that references the direct PAW host
    content = resp.content
    content_type = resp_headers.get("content-type", "")
    if any(ct in content_type for ct in ("text/html", "application/javascript", "text/javascript", "application/json")):
        text = content.decode("utf-8", errors="replace")
        if paw_origin in text:
            text = text.replace(paw_origin, "/paw")
            content = text.encode("utf-8")

    from starlette.responses import Response as RawResponse
    response = RawResponse(
        content=content,
        status_code=resp.status_code,
        headers=resp_headers,
    )
    # Append Set-Cookie headers (supports multiple values)
    for sc in set_cookie_headers:
        response.headers.append("set-cookie", sc)

    return response


@app.api_route("/paw/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def paw_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, path)


@app.api_route("/cdn/{path:path}", methods=["GET"])
async def paw_cdn_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"cdn/{path}")


@app.api_route("/prism/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def paw_prism_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"prism/{path}")


@app.api_route("/perspectives/{path:path}", methods=["GET"])
async def paw_perspectives_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"perspectives/{path}")


@app.api_route("/css/{path:path}", methods=["GET"])
async def paw_css_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"css/{path}")


@app.api_route("/images/{path:path}", methods=["GET"])
async def paw_images_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"images/{path}")


@app.api_route("/wa-share/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def paw_wa_share_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"wa-share/{path}")


@app.api_route("/wa-save/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def paw_wa_save_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"wa-save/{path}")


@app.api_route("/login", methods=["GET", "POST"])
async def paw_login_proxy(request: Request):
    return await _proxy_to_paw(request, "login")


@app.api_route("/login/{path:path}", methods=["GET", "POST"])
async def paw_login_sub_proxy(request: Request, path: str):
    """PAW login page loads /login/styles/*, /login/scripts/*, /login/images/*."""
    return await _proxy_to_paw(request, f"login/{path}")


@app.api_route("/ui/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def paw_ui_proxy(request: Request, path: str):
    """PAW's JS makes direct requests to /ui/* (e.g. /ui/types) without /paw/ prefix."""
    return await _proxy_to_paw(request, f"ui/{path}")


# PAW API paths that its JavaScript requests without /paw/ prefix
@app.api_route("/pacontent/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def paw_pacontent_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"pacontent/{path}")


@app.api_route("/rolemgmt/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def paw_rolemgmt_proxy(request: Request, path: str):
    return await _proxy_to_paw(request, f"rolemgmt/{path}")


@app.api_route("/clog", methods=["GET", "POST"])
async def paw_clog_proxy(request: Request):
    return await _proxy_to_paw(request, "clog")


# ---------------------------------------------------------------------------
# TM1 REST API proxy — PAW's JavaScript calls /api/v1/* for cube data.
# Route directly to TM1 (port 44414) with Basic Auth.
# ---------------------------------------------------------------------------
_tm1_api_client: httpx.AsyncClient | None = None


def _get_tm1_api_client() -> httpx.AsyncClient:
    global _tm1_api_client
    if _tm1_api_client is None:
        from config import settings
        _tm1_api_client = httpx.AsyncClient(
            base_url=f"http://{settings.tm1_host}:{settings.tm1_port}",
            timeout=30.0,
            verify=False,
            follow_redirects=True,
            auth=(settings.tm1_user, settings.tm1_password),
        )
    return _tm1_api_client


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def tm1_api_proxy(request: Request, path: str):
    """Forward TM1 REST API calls from PAW's JavaScript to the TM1 server."""
    client = _get_tm1_api_client()
    url = f"/api/v1/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    fwd_headers = {}
    skip = {"host", "connection", "transfer-encoding", "authorization"}
    for key, value in request.headers.items():
        if key.lower() not in skip:
            fwd_headers[key] = value

    body = await request.body()

    resp = await client.request(
        method=request.method,
        url=url,
        headers=fwd_headers,
        content=body if body else None,
    )

    excluded = {
        "transfer-encoding", "connection", "content-encoding", "content-length",
        "access-control-allow-origin",
    }
    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded
    }
    resp_headers["Access-Control-Allow-Origin"] = "*"
    resp_headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    resp_headers["Access-Control-Allow-Headers"] = "*"

    return StreamingResponse(
        content=iter([resp.content]),
        status_code=resp.status_code,
        headers=resp_headers,
    )


# Serve Vue.js static build from ./static/
STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.is_dir():
    # Serve assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_vue(full_path: str):
        """SPA fallback — always return index.html for non-API routes."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
