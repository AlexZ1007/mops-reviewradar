"""Thin requests wrapper that adds the Supabase access token."""
import os

import requests
import streamlit as st

import auth

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class ApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def request(method: str, path: str, raw: bool = False, **kwargs):
    """`raw=True` returns the response body as bytes (for file downloads) instead of parsing JSON."""
    token = auth.access_token()
    if token is None:
        st.switch_page("Home.py")
    try:
        r = requests.request(
            method, API_BASE_URL + path, headers={"Authorization": f"Bearer {token}"}, timeout=15, **kwargs
        )
    except requests.ConnectionError:
        raise ApiError(0, f"Cannot reach the API at {API_BASE_URL}")
    if r.status_code == 401:
        auth.sign_out()
        st.switch_page("Home.py")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        if isinstance(detail, list):  # FastAPI validation errors
            detail = "; ".join(d.get("msg", str(d)) for d in detail)
        raise ApiError(r.status_code, str(detail))
    if raw:
        return r.content
    return r.json() if r.content else None


def get(path: str):
    return request("GET", path)


def post(path: str, json: dict):
    return request("POST", path, json=json)


def patch(path: str, json: dict):
    return request("PATCH", path, json=json)


def download(path: str) -> bytes:
    """GET a file (the bytes, not JSON)."""
    return request("GET", path, raw=True)


def upload(path: str, file_name: str, data: bytes, content_type: str = "text/csv"):
    """POST one file as multipart form data (the form field is called `file`)."""
    return request("POST", path, files={"file": (file_name, data, content_type)})


def delete(path: str):
    return request("DELETE", path)
