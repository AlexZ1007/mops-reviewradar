"""Entry point: `uv run streamlit run app.py`.

Wraps the multipage app (Home.py + pages/) in an ASGI `st.App` so we can mount one
extra HTTP route that sets the HttpOnly refresh-token cookie (see session_cookie.py).
"""
import streamlit as st
from starlette.routing import Route

import session_cookie

app = st.App("Home.py", routes=[Route(session_cookie.ROUTE_PATH, session_cookie.route, methods=["POST"])])
