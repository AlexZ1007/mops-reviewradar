"""In-app notifications (docs/invite-system.md). Other stories reuse notify()."""
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import InvitationStatus, Notification, Profile, ProjectInvitation
from app.schemas import NotificationOut


def as_utc(dt: datetime) -> datetime:
    """SQLite (tests) returns naive datetimes; Postgres returns aware ones."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def display_name(profile: Profile | None) -> str:
    if profile is None:
        return ""
    return profile.full_name or profile.email


def effective_status(inv: ProjectInvitation) -> InvitationStatus:
    if inv.status == InvitationStatus.pending and as_utc(inv.expires_at) <= datetime.now(UTC):
        return InvitationStatus.expired
    return inv.status


def notify(
    db: Session,
    user_id: uuid.UUID,
    type: str,
    *,
    project_id: int | None = None,
    invitation_id: int | None = None,
    actor: Profile | None = None,
    **payload,
) -> None:
    """Adds a notification to the session; the caller commits."""
    if actor is not None:
        payload.setdefault("actor_name", display_name(actor))
    db.add(
        Notification(
            user_id=user_id,
            type=type,
            project_id=project_id,
            invitation_id=invitation_id,
            actor_id=actor.id if actor else None,
            payload=payload,
        )
    )


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        type=n.type,
        project_id=n.project_id,
        invitation_id=n.invitation_id,
        invitation_status=effective_status(n.invitation) if n.invitation else None,
        actor_id=n.actor_id,
        payload=n.payload or {},
        read_at=n.read_at,
        created_at=n.created_at,
    )


def list_notifications(db: Session, user: Profile, unread_only: bool = False, limit: int = 50) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    return [_out(n) for n in db.scalars(stmt).unique()]


def unread_count(db: Session, user: Profile) -> int:
    return db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    ) or 0


def mark_read(db: Session, user: Profile, notification_id: int) -> None:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
        db.commit()


def mark_all_read(db: Session, user: Profile) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()


def mark_invitation_read(db: Session, invitation_id: int, user_id: uuid.UUID | None = None) -> None:
    """Marks the 'invitation' notifications for an invitation as read (all recipients unless user_id)."""
    stmt = update(Notification).where(
        Notification.invitation_id == invitation_id,
        Notification.type == "invitation",
        Notification.read_at.is_(None),
    )
    if user_id is not None:
        stmt = stmt.where(Notification.user_id == user_id)
    db.execute(stmt.values(read_at=datetime.now(UTC)))
