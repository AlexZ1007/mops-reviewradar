"""/auth/* endpoints: FastAPI as gateway to Supabase Auth. Supabase is faked with httpx.MockTransport."""
import json

import httpx
import pytest

from app.auth.router import get_supabase_auth
from app.auth.supabase_auth import SupabaseAuth
from app.main import app

SESSION = {
    "access_token": "jwt-access",
    "refresh_token": "rt-1",
    "token_type": "bearer",
    "expires_in": 3600,
    "expires_at": 1_900_000_000,
    "user": {"id": "u"},
}


@pytest.fixture
def supabase(client):
    """Install a fake Supabase Auth; returns (calls, set_handler)."""
    calls: list[httpx.Request] = []
    state = {"handler": lambda req: httpx.Response(200, json=SESSION)}

    def transport(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return state["handler"](req)

    fake = SupabaseAuth("http://sb.test", "pub-key", httpx.MockTransport(transport))
    app.dependency_overrides[get_supabase_auth] = lambda: fake

    def set_handler(h):
        state["handler"] = h

    return calls, set_handler


def err(status, code, msg):
    return lambda req: httpx.Response(status, json={"code": status, "error_code": code, "msg": msg})


def test_login_returns_token_pair(client, supabase):
    calls, _ = supabase
    r = client.post("/auth/login", json={"email": " a@x.io ", "password": "secret123"})
    assert r.status_code == 200
    assert r.json() == {
        "access_token": "jwt-access", "refresh_token": "rt-1", "token_type": "bearer",
        "expires_in": 3600, "expires_at": 1_900_000_000,
    }
    req = calls[0]
    assert req.url.path == "/auth/v1/token" and req.url.params["grant_type"] == "password"
    assert req.headers["apikey"] == "pub-key"
    assert json.loads(req.content) == {"email": "a@x.io", "password": "secret123"}


def test_login_wrong_password_401(client, supabase):
    supabase[1](err(400, "invalid_credentials", "Invalid login credentials"))
    r = client.post("/auth/login", json={"email": "a@x.io", "password": "bad"})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid email or password"


def test_login_rate_limited_429(client, supabase):
    supabase[1](err(429, "over_request_rate_limit", "slow down"))
    assert client.post("/auth/login", json={"email": "a@x.io", "password": "x"}).status_code == 429


def test_supabase_down_503(client, supabase):
    def boom(req):
        raise httpx.ConnectError("refused")

    supabase[1](boom)
    assert client.post("/auth/login", json={"email": "a@x.io", "password": "x"}).status_code == 503


def test_signup_sends_full_name(client, supabase):
    calls, _ = supabase
    r = client.post("/auth/signup", json={"email": "n@x.io", "password": "secret123", "full_name": " Ana "})
    assert r.status_code == 201 and r.json()["refresh_token"] == "rt-1"
    assert calls[0].url.path == "/auth/v1/signup"
    assert json.loads(calls[0].content)["data"] == {"full_name": "Ana"}


def test_signup_existing_email_409(client, supabase):
    supabase[1](err(422, "user_already_exists", "User already registered"))
    r = client.post("/auth/signup", json={"email": "n@x.io", "password": "secret123", "full_name": "A"})
    assert r.status_code == 409


def test_signup_weak_password_400_with_message(client, supabase):
    supabase[1](err(422, "weak_password", "Password should be at least 8 characters."))
    r = client.post("/auth/signup", json={"email": "n@x.io", "password": "1", "full_name": "A"})
    assert r.status_code == 400 and "8 characters" in r.json()["detail"]


def test_signup_without_session_400(client, supabase):
    supabase[1](lambda req: httpx.Response(200, json={"id": "u", "email": "n@x.io"}))
    r = client.post("/auth/signup", json={"email": "n@x.io", "password": "secret123", "full_name": "A"})
    assert r.status_code == 400 and "Confirm your email" in r.json()["detail"]


def test_refresh_rotates_token(client, supabase):
    calls, set_handler = supabase
    set_handler(lambda req: httpx.Response(200, json={**SESSION, "refresh_token": "rt-2"}))
    r = client.post("/auth/refresh", json={"refresh_token": "rt-1"})
    assert r.status_code == 200 and r.json()["refresh_token"] == "rt-2"
    assert calls[0].url.params["grant_type"] == "refresh_token"
    assert json.loads(calls[0].content) == {"refresh_token": "rt-1"}


def test_refresh_with_used_or_revoked_token_401(client, supabase):
    supabase[1](err(400, "refresh_token_already_used", "Invalid Refresh Token: Already Used"))
    assert client.post("/auth/refresh", json={"refresh_token": "rt-1"}).status_code == 401


def test_refresh_requires_token_422(client, supabase):
    assert client.post("/auth/refresh", json={}).status_code == 422


def test_logout_revokes_session(client, supabase):
    calls, set_handler = supabase
    set_handler(lambda req: httpx.Response(204))
    r = client.post("/auth/logout", headers={"Authorization": "Bearer jwt-access"})
    assert r.status_code == 204
    assert calls[0].url.path == "/auth/v1/logout" and calls[0].url.params["scope"] == "local"
    assert calls[0].headers["Authorization"] == "Bearer jwt-access"


def test_logout_is_idempotent(client, supabase):
    calls, set_handler = supabase
    set_handler(err(401, "session_not_found", "expired"))
    assert client.post("/auth/logout", headers={"Authorization": "Bearer old"}).status_code == 204
    assert client.post("/auth/logout").status_code == 204
    assert len(calls) == 1
