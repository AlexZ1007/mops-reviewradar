"""Supabase Auth for Streamlit: one supabase-py client per browser session."""
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://127.0.0.1:64321")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")


def client() -> Client:
    if "sb" not in st.session_state:
        st.session_state.sb = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
    return st.session_state.sb


def _error_message(exc: Exception) -> str:
    msg = str(exc)
    if "Invalid login credentials" in msg:
        return "Invalid email or password"
    return msg or "Authentication failed"


def sign_in(email: str, password: str) -> str | None:
    """Returns an error message, or None on success."""
    try:
        client().auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # supabase raises AuthApiError subclasses
        return _error_message(exc)
    return None


def sign_up(email: str, password: str, full_name: str) -> str | None:
    try:
        res = client().auth.sign_up(
            {"email": email, "password": password, "options": {"data": {"full_name": full_name}}}
        )
    except Exception as exc:
        return _error_message(exc)
    if res.session is None:
        return "Account created, but no session was returned. Try signing in."
    return None


def sign_out() -> None:
    try:
        client().auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()


def access_token() -> str | None:
    """Current access token; supabase-py refreshes it when expired."""
    try:
        session = client().auth.get_session()
    except Exception:
        return None
    return session.access_token if session else None


def require_login() -> None:
    """Call at the top of every protected page."""
    if access_token() is None:
        st.switch_page("Home.py")


def nav_header() -> None:
    """Top bar on every signed-in page: Projects, Notifications (with unread badge), Sign out."""
    import api_client  # imported here: api_client imports this module

    try:
        unread = api_client.get("/notifications/unread-count")["count"]
    except api_client.ApiError:
        unread = 0
    c1, c2, _, c3 = st.columns([1.2, 1.8, 2, 1])
    if c1.button("📁 Projects", width="stretch"):
        st.switch_page("pages/1_Projects.py")
    bell = f"🔔 Notifications ({unread})" if unread else "🔔 Notifications"
    if c2.button(bell, width="stretch", type="primary" if unread else "secondary"):
        st.switch_page("pages/3_Notifications.py")
    if c3.button("Sign out", width="stretch"):
        sign_out()
        st.switch_page("Home.py")
