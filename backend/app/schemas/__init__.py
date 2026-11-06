import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import InvitationStatus, ProjectRole


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool


class ProfileUpdate(BaseModel):
    full_name: str = Field(max_length=120)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_by: uuid.UUID | None
    archived_at: datetime | None
    created_at: datetime
    my_role: ProjectRole | None = None


class InvitationCreate(BaseModel):
    # Basic shape check only. EmailStr would reject special-use domains like .local.
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+$", max_length=320)
    role: ProjectRole


class MemberUpdate(BaseModel):
    role: ProjectRole


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: ProjectRole
    joined_at: datetime


class InvitationOut(BaseModel):
    id: int
    project_id: int
    email: str
    role: ProjectRole
    status: InvitationStatus  # effective: a pending invitation past expires_at is reported as expired
    invited_by: uuid.UUID | None
    invited_by_name: str | None
    created_at: datetime
    expires_at: datetime


class NotificationOut(BaseModel):
    id: int
    type: str
    project_id: int | None
    invitation_id: int | None
    invitation_status: InvitationStatus | None  # live status, so stale Accept buttons can be hidden
    actor_id: uuid.UUID | None
    payload: dict
    read_at: datetime | None
    created_at: datetime


class UnreadCount(BaseModel):
    count: int
