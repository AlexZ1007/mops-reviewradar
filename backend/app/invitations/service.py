"""Project invitation rules (docs/invite-system.md section 3)."""
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext
from app.models import InvitationStatus, Profile, ProjectInvitation, ProjectMember, ProjectRole
from app.notifications.service import display_name, effective_status, mark_invitation_read, notify
from app.projects.service import _audit, project_out
from app.schemas import InvitationOut, ProjectOut

INVITATION_TTL = timedelta(days=7)
ALREADY_INVITED = "Already invited. Revoke the pending invitation to change the role."


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")


def _out(inv: ProjectInvitation) -> InvitationOut:
    return InvitationOut(
        id=inv.id,
        project_id=inv.project_id,
        email=inv.email,
        role=inv.role,
        status=effective_status(inv),
        invited_by=inv.invited_by,
        invited_by_name=display_name(inv.inviter) or None,
        created_at=inv.created_at,
        expires_at=inv.expires_at,
    )


def _profile_by_email(db: Session, email: str) -> Profile | None:
    return db.scalar(select(Profile).where(func.lower(Profile.email) == email.lower()))


def _pending(db: Session, project_id: int, email: str) -> ProjectInvitation | None:
    return db.scalars(
        select(ProjectInvitation).where(
            ProjectInvitation.project_id == project_id,
            func.lower(ProjectInvitation.email) == email.lower(),
            ProjectInvitation.status == InvitationStatus.pending,
        )
    ).first()


# Owner side ---------------------------------------------------------------------

def create_invitation(db: Session, ctx: ProjectContext, email: str, role: ProjectRole) -> InvitationOut:
    email = email.strip().lower()
    project_id = ctx.project.id
    profile = _profile_by_email(db, email)
    if profile is not None and db.get(ProjectMember, (project_id, profile.id)) is not None:
        raise _conflict("Already a member of this project")
    existing = _pending(db, project_id, email)
    if existing is not None:
        if effective_status(existing) != InvitationStatus.expired:
            raise _conflict(ALREADY_INVITED)
        existing.status = InvitationStatus.expired  # frees the one-pending-per-email slot
        db.flush()

    inv = ProjectInvitation(
        project_id=project_id,
        email=email,
        role=role,
        invited_by=ctx.user.id,
        expires_at=datetime.now(UTC) + INVITATION_TTL,
    )
    db.add(inv)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _conflict(ALREADY_INVITED)
    # Unknown or inactive emails get the same response (no account enumeration). Users who
    # sign up later get the notification from the on_profile_created trigger.
    if profile is not None and profile.is_active:
        notify(db, profile.id, "invitation", project_id=project_id, invitation_id=inv.id, actor=ctx.user,
               project_name=ctx.project.name, role=role.value)
    _audit(db, project_id, ctx.user, "invitation.created", invitation_id=inv.id, email=email, role=role.value)
    db.commit()
    db.refresh(inv)
    return _out(inv)


def list_invitations(db: Session, ctx: ProjectContext) -> list[InvitationOut]:
    invitations = db.scalars(
        select(ProjectInvitation)
        .where(ProjectInvitation.project_id == ctx.project.id, ProjectInvitation.status == InvitationStatus.pending)
        .order_by(ProjectInvitation.created_at.desc(), ProjectInvitation.id.desc())
    ).unique()
    return [_out(i) for i in invitations]


def revoke_invitation(db: Session, ctx: ProjectContext, invitation_id: int) -> None:
    inv = db.get(ProjectInvitation, invitation_id)
    if inv is None or inv.project_id != ctx.project.id:
        raise _not_found()
    if inv.status != InvitationStatus.pending:
        raise _conflict(f"Invitation is already {inv.status.value}")
    inv.status = InvitationStatus.revoked
    inv.responded_by = ctx.user.id
    inv.responded_at = datetime.now(UTC)
    mark_invitation_read(db, inv.id)
    _audit(db, inv.project_id, ctx.user, "invitation.revoked", invitation_id=inv.id, email=inv.email)
    db.commit()


# Invitee side -------------------------------------------------------------------

def _for_invitee(db: Session, user: Profile, invitation_id: int) -> ProjectInvitation:
    """Loads an invitation the user may answer, or raises 404/409 (rules 6-7)."""
    inv = db.get(ProjectInvitation, invitation_id)
    if inv is None or inv.email.lower() != user.email.lower():
        raise _not_found()
    current = effective_status(inv)
    if current == InvitationStatus.expired:
        if inv.status == InvitationStatus.pending:
            inv.status = InvitationStatus.expired
            mark_invitation_read(db, inv.id, user.id)
            db.commit()
        raise _conflict("This invitation has expired")
    if current != InvitationStatus.pending:
        raise _conflict(f"This invitation was already {current.value}")
    if inv.project.archived_at is not None:
        raise _conflict("This project has been archived")
    return inv


def _close(db: Session, inv: ProjectInvitation, user: Profile, new_status: InvitationStatus) -> None:
    inv.status = new_status
    inv.responded_by = user.id
    inv.responded_at = datetime.now(UTC)
    mark_invitation_read(db, inv.id, user.id)
    if inv.invited_by is not None and inv.invited_by != user.id:
        notify(db, inv.invited_by, f"invitation.{new_status.value}", project_id=inv.project_id,
               invitation_id=inv.id, actor=user, project_name=inv.project.name, role=inv.role.value)
    _audit(db, inv.project_id, user, f"invitation.{new_status.value}", invitation_id=inv.id, email=inv.email)


def accept_invitation(db: Session, user: Profile, invitation_id: int) -> ProjectOut:
    inv = _for_invitee(db, user, invitation_id)
    member = db.get(ProjectMember, (inv.project_id, user.id))
    _close(db, inv, user, InvitationStatus.accepted)
    if member is None:  # already a member: the invitation is just closed (idempotent)
        member = ProjectMember(project_id=inv.project_id, user_id=user.id, role=inv.role, added_by=inv.invited_by)
        db.add(member)
        _audit(db, inv.project_id, user, "member.added", user_id=user.id, role=inv.role.value,
               invitation_id=inv.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("You are already a member of this project")
    return project_out(inv.project, member.role)


def decline_invitation(db: Session, user: Profile, invitation_id: int) -> None:
    inv = _for_invitee(db, user, invitation_id)
    _close(db, inv, user, InvitationStatus.declined)
    db.commit()
