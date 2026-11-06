from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext, get_current_user, require_permission
from app.db import get_db
from app.invitations import service
from app.models import Profile
from app.schemas import InvitationCreate, InvitationOut, ProjectOut

router = APIRouter(tags=["invitations"])


@router.post("/projects/{project_id}/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
def create_invitation(
    data: InvitationCreate,
    ctx: ProjectContext = Depends(require_permission("members.manage")),
    db: Session = Depends(get_db),
) -> InvitationOut:
    return service.create_invitation(db, ctx, data.email, data.role)


@router.get("/projects/{project_id}/invitations", response_model=list[InvitationOut])
def list_invitations(
    ctx: ProjectContext = Depends(require_permission("members.manage")),
    db: Session = Depends(get_db),
) -> list[InvitationOut]:
    return service.list_invitations(db, ctx)


@router.delete("/projects/{project_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: int,
    ctx: ProjectContext = Depends(require_permission("members.manage")),
    db: Session = Depends(get_db),
) -> Response:
    service.revoke_invitation(db, ctx, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invitations/{invitation_id}/accept", response_model=ProjectOut)
def accept_invitation(
    invitation_id: int, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProjectOut:
    return service.accept_invitation(db, user, invitation_id)


@router.post("/invitations/{invitation_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invitation(
    invitation_id: int, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    service.decline_invitation(db, user, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
