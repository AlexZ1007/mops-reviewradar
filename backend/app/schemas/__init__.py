import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ProjectRole


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


class MemberCreate(BaseModel):
    # Basic shape check only: the address must match an existing profile, which Supabase
    # already validated at sign-up. EmailStr would reject special-use domains like .local.
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
