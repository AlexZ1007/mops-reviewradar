"""Session handling for Streamlit: Supabase JWT access token + rotating refresh token.

All Supabase Auth calls go through FastAPI (/auth/login, /auth/signup, /auth/refresh,
/auth/logout). The token pair lives in `st.session_state.auth`; the refresh token is
also mirrored into an HttpOnly cookie (see session_cookie.py) so a page reload or a
new tab restores the session instead of logging the user out.
"""
import os
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

import session_cookie

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REFRESH_MARGIN = 60  # refresh the access token this many seconds before it expires


class _AuthCallFailed(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _call(path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.post(API_BASE_URL + path, json=body or {}, headers=headers, timeout=15)
    except requests.RequestException:
        raise _AuthCallFailed(0, f"Cannot reach the API at {API_BASE_URL}")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        if isinstance(detail, list):  # FastAPI validation errors
            detail = "; ".join(d.get("msg", str(d)) for d in detail)
        raise _AuthCallFailed(r.status_code, str(detail) or "Authentication failed")
    return r.json() if r.content else {}


# Cookie sync -------------------------------------------------------------------

def _queue_cookie(refresh_token: str | None) -> None:
    st.session_state.cookie_nonce = session_cookie.queue(refresh_token)


def sync_cookie() -> None:
    """Render the pending cookie write/clear, if any. Called on every page (via require_login / Home).

    The element is re-rendered on each run until the browser has posted the nonce, so a
    write queued right before `st.switch_page` still lands on the next page.
    """
    nonce = st.session_state.get("cookie_nonce")
    if not nonce:
        return
    if session_cookie.status(nonce) != "pending":
        del st.session_state.cookie_nonce
        return
    with st.container(key="rr-cookie-sync", height=1, border=False):
        st.html(session_cookie.browser_script(nonce), unsafe_allow_javascript=True)


# Session -------------------------------------------------------------------------

def _store(tokens: dict) -> None:
    st.session_state.auth = tokens
    st.session_state.pop("signed_out", None)
    _queue_cookie(tokens["refresh_token"])


def _drop_session() -> None:
    st.session_state.pop("auth", None)
    _queue_cookie(None)


def _refresh(refresh_token: str) -> bool:
    """Exchange the refresh token for a new pair. False when the session is gone (revoked/expired)."""
    try:
        _store(_call("/auth/refresh", {"refresh_token": refresh_token}))
        return True
    except _AuthCallFailed as exc:
        if exc.status == 401:
            _drop_session()
        return False


def _restore_from_cookie() -> dict | None:
    """First run of a new browser session (reload, new tab): try the HttpOnly refresh cookie."""
    if st.session_state.get("signed_out") or st.session_state.get("restore_tried"):
        return None
    st.session_state.restore_tried = True
    refresh_token = st.context.cookies.get(session_cookie.COOKIE_NAME)
    if not refresh_token:
        return None
    _refresh(refresh_token)
    return st.session_state.get("auth")


def _error_message(exc: _AuthCallFailed) -> str:
    return exc.detail or "Authentication failed"


def sign_in(email: str, password: str) -> str | None:
    """Returns an error message, or None on success."""
    try:
        _store(_call("/auth/login", {"email": email, "password": password}))
    except _AuthCallFailed as exc:
        return _error_message(exc)
    return None


def sign_up(email: str, password: str, full_name: str) -> str | None:
    try:
        _store(_call("/auth/signup", {"email": email, "password": password, "full_name": full_name}))
    except _AuthCallFailed as exc:
        return _error_message(exc)
    return None


def sign_out() -> None:
    """Revoke the Supabase session, clear local state and the refresh cookie."""
    session = st.session_state.get("auth")
    if session:
        try:
            _call("/auth/logout", token=session["access_token"])
        except _AuthCallFailed:
            pass
    st.session_state.clear()
    st.session_state.signed_out = True  # do not restore from the (stale) cookie snapshot of this connection
    _queue_cookie(None)


def access_token() -> str | None:
    """A valid access token, refreshed shortly before expiry; None when signed out."""
    session = st.session_state.get("auth") or _restore_from_cookie()
    if session is None:
        return None
    if session["expires_at"] - REFRESH_MARGIN <= time.time():
        if not _refresh(session["refresh_token"]):
            session = st.session_state.get("auth")
            # transient failure (API down): keep using the token while it is still valid
            if session is None or session["expires_at"] <= time.time():
                return None
            return session["access_token"]
        session = st.session_state.auth
    return session["access_token"]


def require_login() -> None:
    """Call at the top of every protected page."""
    if access_token() is None:
        st.switch_page("Home.py")
    sync_cookie()
