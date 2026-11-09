from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import Profile
from app.notifications import service
from app.schemas import NotificationOut, UnreadCount

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread: bool = False,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    return service.list_notifications(db, user, unread_only=unread)


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)) -> UnreadCount:
    return UnreadCount(count=service.unread_count(db, user))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    service.mark_all_read(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    notification_id: int, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    service.mark_read(db, user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
