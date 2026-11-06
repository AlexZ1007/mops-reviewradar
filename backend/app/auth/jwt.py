"""Supabase access-token verification.

Asymmetric signing keys (ES256/RS256) are verified against the project JWKS.
Legacy HS256 projects (including the default local Supabase CLI stack) use the shared JWT secret.
"""
from typing import Any

import jwt
from jwt import PyJWKClient

AUDIENCE = "authenticated"
ASYMMETRIC_ALGS = ["ES256", "RS256"]


class InvalidToken(Exception):
    pass


class TokenVerifier:
    def __init__(self, jwks_client: PyJWKClient | None, hs256_secret: str = "") -> None:
        self.jwks_client = jwks_client
        self.hs256_secret = hs256_secret

    @classmethod
    def for_supabase(cls, supabase_url: str, hs256_secret: str = "") -> "TokenVerifier":
        jwks_url = supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        return cls(PyJWKClient(jwks_url, cache_keys=True, lifespan=600), hs256_secret)

    def verify(self, token: str) -> dict[str, Any]:
        try:
            alg = jwt.get_unverified_header(token).get("alg")
            if alg == "HS256":
                if not self.hs256_secret:
                    raise InvalidToken("HS256 tokens are not accepted")
                key: Any = self.hs256_secret
                algorithms = ["HS256"]
            else:
                if self.jwks_client is None:
                    raise InvalidToken("No JWKS configured")
                key = self.jwks_client.get_signing_key_from_jwt(token).key
                algorithms = ASYMMETRIC_ALGS
            return jwt.decode(
                token,
                key,
                algorithms=algorithms,
                audience=AUDIENCE,
                options={"require": ["exp", "sub", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc
