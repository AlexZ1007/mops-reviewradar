from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.dependencies import bearer, get_current_user
from app.auth.supabase_auth import AuthError, SupabaseAuth
from app.config import get_settings
from app.db import get_db
from app.models import Profile
from app.schemas import LoginIn, ProfileOut, ProfileUpdate, RefreshIn, SignUpIn, TokenOut

router = APIRouter(tags=["auth"])


@lru_cache
def get_supabase_auth() -> SupabaseAuth:
    settings = get_settings()
    return SupabaseAuth(settings.supabase_url, settings.supabase_publishable_key)


def _tokens(data: dict[str, Any]) -> TokenOut:
    return TokenOut(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"],
        expires_at=data["expires_at"],
    )


def _upstream_error(exc: AuthError) -> HTTPException:
    if exc.status == 0 or exc.status >= 500:
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service is unavailable")
    if exc.status == 429:
        return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try again in a few minutes")
    return HTTPException(status.HTTP_400_BAD_REQUEST, exc.message or "Authentication failed")


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, sb: SupabaseAuth = Depends(get_supabase_auth)) -> TokenOut:
    try:
        return _tokens(sb.sign_in(data.email.strip(), data.password))
    except AuthError as exc:
        if exc.status == 400 and exc.code in ("invalid_credentials", "invalid_grant", ""):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
        raise _upstream_error(exc)


@router.post("/auth/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(data: SignUpIn, sb: SupabaseAuth = Depends(get_supabase_auth)) -> TokenOut:
    try:
        res = sb.sign_up(data.email.strip(), data.password, data.full_name.strip())
    except AuthError as exc:
        if exc.code in ("user_already_exists", "email_exists"):
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
        raise _upstream_error(exc)
    if "access_token" not in res:  # email confirmation is on in Supabase: no session yet
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Account created. Confirm your email, then sign in.")
    return _tokens(res)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, sb: SupabaseAuth = Depends(get_supabase_auth)) -> TokenOut:
    try:
        return _tokens(sb.refresh(data.refresh_token))
    except AuthError as exc:
        if 400 <= exc.status < 500 and exc.status != 429:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, sign in again")
        raise _upstream_error(exc)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    sb: SupabaseAuth = Depends(get_supabase_auth),
) -> Response:
    """Revokes the session's refresh tokens. Idempotent: an already-expired session is not an error."""
    if cred is not None:
        try:
            sb.sign_out(cred.credentials)
        except AuthError:
            pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=ProfileOut)
def read_me(user: Profile = Depends(get_current_user)) -> Profile:
    return user


@router.patch("/me", response_model=ProfileOut)
def update_me(
    data: ProfileUpdate,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    user.full_name = data.full_name.strip()
    db.commit()
    return user
