import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ImportStatus, InvitationStatus, ProjectRole, ReviewSource


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class SignUpIn(LoginIn):
    full_name: str = Field(min_length=1, max_length=120)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class TokenOut(BaseModel):
    """Supabase session: JWT access token + single-use refresh token."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: int  # unix seconds


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


COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


def _clean_category_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Name is required")
    return value


def _lower_color(value: str | None) -> str | None:
    return value.lower() if value else value


class CategoryCreate(BaseModel):
    name: str = Field(max_length=80)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)  # #RRGGBB

    _name = field_validator("name")(_clean_category_name)
    _color = field_validator("color")(_lower_color)


class CategoryUpdate(BaseModel):
    """Partial update: omitted fields are untouched, `"color": null` clears the color."""

    name: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("Name can't be null")
        return _clean_category_name(v)

    _color = field_validator("color")(_lower_color)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    color: str | None
    created_at: datetime


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


# Reviews and imports (stories #6 and #9) ---------------------------------------------

MAX_REVIEW_LENGTH = 10_000
MAX_TEXT_FIELD = 120  # author, external_id


def _clean_review_content(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Content is required")
    return value


def _blank_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


class ReviewCreate(BaseModel):
    """A review typed in by hand. Only `content` is required."""

    content: str = Field(max_length=MAX_REVIEW_LENGTH)
    rating: int | None = Field(default=None, ge=1, le=5)
    author: str | None = Field(default=None, max_length=MAX_TEXT_FIELD)
    reviewed_at: datetime | None = None  # date of the original review
    category_id: int | None = None

    _content = field_validator("content")(_clean_review_content)
    _author = field_validator("author")(_blank_to_none)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    import_id: int | None
    category_id: int | None
    created_by: uuid.UUID | None
    source: ReviewSource
    external_id: str | None
    author: str | None
    rating: int | None
    content: str
    reviewed_at: datetime | None
    created_at: datetime


class ImportErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_number: int  # spreadsheet numbering: the header is row 1, the first review row 2
    field: str | None
    message: str


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    uploaded_by: uuid.UUID | None
    file_name: str
    status: ImportStatus
    total_rows: int
    imported_rows: int
    duplicate_rows: int
    invalid_rows: int
    created_at: datetime
    finished_at: datetime | None
    repeat_of: int | None = None  # the first earlier import of this very same file, if there is one


class ImportDuplicateOut(BaseModel):
    """A row that was skipped because the same text already exists. Only given right after an upload."""

    row_number: int
    content: str  # shortened
    of_review_id: int | None  # the same text was already saved as this review...
    of_row: int | None  # ...or appears earlier in this file, at this row


class ImportDetailOut(ImportOut):
    errors: list[ImportErrorOut]
    duplicates: list[ImportDuplicateOut] = []
