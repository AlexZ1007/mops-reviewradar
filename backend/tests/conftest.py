import time
import uuid
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_token_verifier
from app.auth.jwt import TokenVerifier
from app.db import Base, get_db
from app.main import app
from app.models import Profile

KID = "test-key"


class FakeJWKS:
    """Stands in for PyJWKClient: serves one locally generated public key."""

    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        if jwt.get_unverified_header(token).get("kid") != KID:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return SimpleNamespace(key=self.public_key)


@pytest.fixture(scope="session")
def private_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def verifier(private_key):
    return TokenVerifier(FakeJWKS(private_key.public_key()))


@pytest.fixture
def make_token(private_key):
    def _make(sub, *, aud="authenticated", exp_in=3600, kid=KID, key=None):
        claims = {"sub": str(sub), "aud": aud, "exp": int(time.time()) + exp_in, "role": "authenticated"}
        return jwt.encode(claims, key or private_key, algorithm="ES256", headers={"kid": kid})

    return _make


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine, expire_on_commit=False)
    with Session() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db, verifier):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_token_verifier] = lambda: verifier
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db):
    def _make(email, *, is_active=True, full_name=""):
        user = Profile(id=uuid.uuid4(), email=email, full_name=full_name, is_active=is_active)
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def auth(make_token):
    def _headers(user):
        return {"Authorization": f"Bearer {make_token(user.id)}"}

    return _headers
