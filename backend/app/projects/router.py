import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext, get_current_user, require_permission
from app.db import get_db
from app.models import Profile
from app.projects import service
from app.schemas import MemberCreate, MemberOut, MemberUpdate, ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    return service.create_project(db, user, data)


@router.get("", response_model=list[ProjectOut])
def list_projects(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProjectOut]:
    return service.list_projects(db, user)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(ctx: ProjectContext = Depends(require_permission("project.read"))) -> ProjectOut:
    return service.project_out(ctx.project, ctx.role)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    data: ProjectUpdate,
    ctx: ProjectContext = Depends(require_permission("project.update")),
    db: Session = Depends(get_db),
) -> ProjectOut:
    return service.update_project(db, ctx, data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_project(
    ctx: ProjectContext = Depends(require_permission("project.update")),
    db: Session = Depends(get_db),
) -> Response:
    service.archive_project(db, ctx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/members", response_model=list[MemberOut])
def list_members(
    ctx: ProjectContext = Depends(require_permission("project.read")),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    return service.list_members(db, ctx)


@router.post("/{project_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    data: MemberCreate,
    ctx: ProjectContext = Depends(require_permission("members.manage")),
    db: Session = Depends(get_db),
) -> MemberOut:
    return service.add_member(db, ctx, data.email, data.role)


@router.patch("/{project_id}/members/{user_id}", response_model=MemberOut)
def change_role(
    user_id: uuid.UUID,
    data: MemberUpdate,
    ctx: ProjectContext = Depends(require_permission("members.manage")),
    db: Session = Depends(get_db),
) -> MemberOut:
    return service.change_role(db, ctx, user_id, data.role)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: uuid.UUID,
    # project.read here; members.manage is checked in the service unless the user is leaving.
    ctx: ProjectContext = Depends(require_permission("project.read")),
    db: Session = Depends(get_db),
) -> Response:
    if ctx.project.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Project is archived")
    service.remove_member(db, ctx, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
