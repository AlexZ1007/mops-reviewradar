"""SQLAlchemy models mapping the tables created by supabase/migrations.

Schema changes go through Supabase migrations, not these models. Types use portable
variants so the test suite can create the same tables on SQLite.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

BigId = BigInteger().with_variant(Integer, "sqlite")


class ProjectRole(str, enum.Enum):
    owner = "owner"
    analyst = "analyst"
    product_manager = "product_manager"
    viewer = "viewer"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # CITEXT in Postgres
    full_name: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[int] = mapped_column(
        BigId, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[ProjectRole] = mapped_column(
        Enum(ProjectRole, name="project_role", create_type=False)
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped[Profile] = relationship(foreign_keys=[user_id], lazy="joined")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("projects.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[int | None] = mapped_column(BigId)
    details: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigId, ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str | None] = mapped_column(String(7))  # #rrggbb, lower case
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvitationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    revoked = "revoked"
    expired = "expired"


class ProjectInvitation(Base):
    __tablename__ = "project_invitations"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigId, ForeignKey("projects.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320))  # CITEXT in Postgres
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole, name="project_role", create_type=False))
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, name="invitation_status", create_type=False), default=InvitationStatus.pending
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    responded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(lazy="joined")
    inviter: Mapped[Profile | None] = relationship(foreign_keys=[invited_by], lazy="joined")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40))
    project_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("projects.id", ondelete="CASCADE"))
    invitation_id: Mapped[int | None] = mapped_column(
        BigId, ForeignKey("project_invitations.id", ondelete="CASCADE")
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    payload: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invitation: Mapped[ProjectInvitation | None] = relationship(lazy="joined")


class ReviewSource(str, enum.Enum):
    csv = "csv"
    manual = "manual"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Import(Base):
    """One uploaded CSV file and the outcome of processing it (story #6)."""

    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigId, ForeignKey("projects.id", ondelete="CASCADE"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status", create_type=False), default=ImportStatus.pending
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    errors: Mapped[list["ImportRowError"]] = relationship(order_by="ImportRowError.row_number, ImportRowError.id")


class ImportRowError(Base):
    """A problem found in one CSV row. (Not named ImportError: that is a Python builtin.)"""

    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    import_id: Mapped[int] = mapped_column(BigId, ForeignKey("imports.id", ondelete="CASCADE"))
    row_number: Mapped[int] = mapped_column(Integer)
    field: Mapped[str | None] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("project_id", "content_hash", name="uq_reviews_project_content_hash"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigId, ForeignKey("projects.id", ondelete="CASCADE"))
    import_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("imports.id", ondelete="SET NULL"))
    category_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("categories.id", ondelete="SET NULL"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    source: Mapped[ReviewSource] = mapped_column(Enum(ReviewSource, name="review_source", create_type=False))
    external_id: Mapped[str | None] = mapped_column(String(120))
    author: Mapped[str | None] = mapped_column(String(120))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 of normalized content
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
