"""Thin client for the Supabase Auth (GoTrue) REST API.

FastAPI is the only caller: the frontend never talks to Supabase directly.
Supabase issues the JWT access token (short-lived) and the opaque refresh token
(single-use, rotated on every refresh when `enable_refresh_token_rotation` is on).
"""
from dataclasses import dataclass
from typing import Any

import httpx

TIMEOUT = 10.0


class AuthError(Exception):
    """Supabase Auth rejected the request. `status` is the Supabase HTTP status (0 = unreachable)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class SupabaseAuth:
    url: str
    api_key: str
    transport: httpx.BaseTransport | None = None  # tests inject httpx.MockTransport

    def _post(self, path: str, body: dict[str, Any] | None = None, *, bearer: str | None = None) -> dict[str, Any]:
        headers = {"apikey": self.api_key}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        try:
            with httpx.Client(base_url=self.url.rstrip("/") + "/auth/v1", timeout=TIMEOUT, transport=self.transport) as c:
                r = c.post(path, json=body or {}, headers=headers)
        except httpx.HTTPError as exc:
            raise AuthError(0, "unreachable", "Authentication service is unavailable") from exc
        if r.status_code >= 400:
            try:
                data = r.json()
            except ValueError:
                data = {}
            code = str(data.get("error_code") or data.get("error") or "")
            message = data.get("msg") or data.get("message") or data.get("error_description") or r.text
            raise AuthError(r.status_code, code, str(message))
        return r.json() if r.content else {}

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        return self._post("/token?grant_type=password", {"email": email, "password": password})

    def sign_up(self, email: str, password: str, full_name: str) -> dict[str, Any]:
        return self._post("/signup", {"email": email, "password": password, "data": {"full_name": full_name}})

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._post("/token?grant_type=refresh_token", {"refresh_token": refresh_token})

    def sign_out(self, access_token: str) -> None:
        """Revokes the refresh tokens of this session (scope=local). The access JWT stays valid until `exp`."""
        self._post("/logout?scope=local", bearer=access_token)
