import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.jwt import InvalidToken, TokenVerifier


# JWT verification --------------------------------------------------------------

def test_valid_token_accepted(verifier, make_token):
    sub = uuid.uuid4()
    assert verifier.verify(make_token(sub))["sub"] == str(sub)


def test_expired_token_rejected(verifier, make_token):
    with pytest.raises(InvalidToken):
        verifier.verify(make_token(uuid.uuid4(), exp_in=-10))


def test_wrong_audience_rejected(verifier, make_token):
    with pytest.raises(InvalidToken):
        verifier.verify(make_token(uuid.uuid4(), aud="anon"))


def test_unknown_signing_key_rejected(verifier, make_token):
    with pytest.raises(InvalidToken):
        verifier.verify(make_token(uuid.uuid4(), kid="other"))


def test_token_signed_with_other_key_rejected(verifier, make_token):
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(InvalidToken):
        verifier.verify(make_token(uuid.uuid4(), key=other))


def test_garbage_token_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify("not-a-jwt")


def test_hs256_accepted_only_with_secret():
    secret = "x" * 40
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": int(time.time()) + 60}, secret, algorithm="HS256"
    )
    assert TokenVerifier(None, secret).verify(token)["aud"] == "authenticated"
    with pytest.raises(InvalidToken):
        TokenVerifier(None, "").verify(token)


# /me -------------------------------------------------------------------------

def test_missing_header_401(client):
    assert client.get("/me").status_code == 401


def test_invalid_token_401(client):
    assert client.get("/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_token_without_profile_401(client, make_token):
    r = client.get("/me", headers={"Authorization": f"Bearer {make_token(uuid.uuid4())}"})
    assert r.status_code == 401


def test_inactive_profile_401(client, make_user, auth):
    user = make_user("off@x.io", is_active=False)
    assert client.get("/me", headers=auth(user)).status_code == 401


def test_me_returns_profile(client, make_user, auth):
    user = make_user("me@x.io", full_name="Me")
    r = client.get("/me", headers=auth(user))
    assert r.status_code == 200
    assert r.json() == {"id": str(user.id), "email": "me@x.io", "full_name": "Me", "is_active": True}


def test_update_me(client, make_user, auth):
    user = make_user("me@x.io")
    r = client.patch("/me", json={"full_name": "  Ana  "}, headers=auth(user))
    assert r.status_code == 200 and r.json()["full_name"] == "Ana"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
