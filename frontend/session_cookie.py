"""HttpOnly refresh-token cookie for the Streamlit frontend.

Streamlit scripts run over a websocket and cannot set cookies, and `st.session_state`
dies with the browser tab's connection, so a page reload would log the user out.

Flow:
1. The script queues a cookie operation (set refresh token / clear) under a random,
   single-use nonce in this process-level store.
2. It renders a tiny `<script>` that POSTs the nonce to `/api/session-cookie`.
3. That Starlette route (mounted in app.py) pops the operation and answers with
   `Set-Cookie: rr_refresh=...; HttpOnly; SameSite=Strict`.
4. On a reload, the new Streamlit session reads the cookie from `st.context.cookies`
   and exchanges it at FastAPI `/auth/refresh` for a fresh token pair.

The refresh token never reaches page JavaScript: only the nonce does.
"""
import os
import secrets
import threading
import time
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response

COOKIE_NAME = "rr_refresh"
COOKIE_MAX_AGE = int(os.environ.get("SESSION_COOKIE_DAYS", "7")) * 24 * 3600
ROUTE_PATH = "/api/session-cookie"
NONCE_TTL = 300  # seconds an unused operation is kept


@dataclass
class _Op:
    value: str | None  # refresh token to store, or None to clear the cookie
    created: float
    done: bool = False


_ops: dict[str, _Op] = {}
_lock = threading.Lock()


def _prune(now: float) -> None:
    for nonce in [n for n, op in _ops.items() if now - op.created > NONCE_TTL]:
        del _ops[nonce]


def queue(value: str | None) -> str:
    """Register a cookie operation; returns the nonce the browser must post."""
    nonce = secrets.token_urlsafe(24)
    with _lock:
        now = time.time()
        _prune(now)
        _ops[nonce] = _Op(value, now)
    return nonce


def status(nonce: str) -> str:
    """'done', 'pending' or 'gone' (expired or unknown)."""
    with _lock:
        op = _ops.get(nonce)
        if op is None:
            return "gone"
        if op.done:
            del _ops[nonce]
            return "done"
        return "pending"


def _take(nonce: str) -> _Op | None:
    with _lock:
        op = _ops.get(nonce)
        if op is None or op.done or time.time() - op.created > NONCE_TTL:
            return None
        op.done = True
        value_op = _Op(op.value, op.created)
        op.value = None  # do not keep the token in memory longer than needed
        return value_op


def browser_script(nonce: str) -> str:
    return (
        "<script>fetch(" + repr(ROUTE_PATH) + ",{method:'POST',credentials:'same-origin',"
        "headers:{'Content-Type':'application/json'},body:JSON.stringify({nonce:" + repr(nonce) + "})})"
        "</script>"
    )


async def route(request: Request) -> Response:
    try:
        nonce = (await request.json()).get("nonce", "")
    except ValueError:
        return Response(status_code=400)
    op = _take(str(nonce))
    if op is None:
        return Response(status_code=404)
    resp = Response(status_code=204, headers={"Cache-Control": "no-store"})
    secure = request.url.scheme == "https"
    if op.value:
        resp.set_cookie(
            COOKIE_NAME, op.value, max_age=COOKIE_MAX_AGE, path="/", httponly=True, samesite="strict", secure=secure
        )
    else:
        resp.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict", secure=secure)
    return resp
