import uuid
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import InvalidToken, TokenVerifier
from app.config import get_settings
from app.db import get_db
from app.models import Profile, Project, ProjectMember, ProjectRole
from app.projects.permissions import PERMISSIONS, READ_ONLY, has_permission

bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache
def get_token_verifier() -> TokenVerifier:
    settings = get_settings()
    return TokenVerifier.for_supabase(settings.supabase_url, settings.supabase_jwt_secret)


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    verifier: TokenVerifier = Depends(get_token_verifier),
    db: Session = Depends(get_db),
) -> Profile:
    if cred is None:
        raise _unauthorized()
    try:
        claims = verifier.verify(cred.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (InvalidToken, ValueError):
        raise _unauthorized()
    profile = db.get(Profile, user_id)
    if profile is None or not profile.is_active:
        raise _unauthorized()
    return profile


@dataclass
class ProjectContext:
    project: Project
    user: Profile
    role: ProjectRole | None  # None when a platform admin is not a member

    def can(self, permission: str) -> bool:
        return self.user.is_admin or has_permission(self.role, permission)


def require_permission(permission: str):
    """Dependency factory implementing the flowchart in docs/auth-and-roles.md."""
    if permission not in PERMISSIONS:
        raise KeyError(f"Unknown permission: {permission}")

    def checker(
        project_id: int,
        user: Profile = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> ProjectContext:
        project = db.get(Project, project_id)
        member = db.get(ProjectMember, (project_id, user.id)) if project else None
        ctx = ProjectContext(project=project, user=user, role=member.role if member else None)
        if project is None or (member is None and not user.is_admin):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        if not ctx.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project role")
        if project.archived_at is not None and permission not in READ_ONLY:
            raise HTTPException(status.HTTP_409_CONFLICT, "Project is archived")
        return ctx

    return checker
