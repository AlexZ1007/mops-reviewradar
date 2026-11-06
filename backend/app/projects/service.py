"""Project and membership business rules (docs/auth-and-roles.md section 3)."""
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext
from app.models import AuditLog, Profile, Project, ProjectMember, ProjectRole
from app.schemas import MemberOut, ProjectCreate, ProjectOut, ProjectUpdate


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def _audit(db: Session, project_id: int, actor: Profile, action: str, **details) -> None:
    db.add(
        AuditLog(
            project_id=project_id,
            actor_id=actor.id,
            action=action,
            target_type="user" if "user_id" in details else "project",
            target_id=None if "user_id" in details else project_id,
            details={k: str(v) if isinstance(v, uuid.UUID) else v for k, v in details.items()} or None,
        )
    )


def _name_taken(db: Session, creator_id: uuid.UUID | None, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(Project.id).where(
        Project.created_by == creator_id,
        func.lower(Project.name) == name.lower(),
        Project.archived_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(Project.id != exclude_id)
    return db.scalar(stmt.limit(1)) is not None


def project_out(project: Project, role: ProjectRole | None) -> ProjectOut:
    return ProjectOut.model_validate(project).model_copy(update={"my_role": role})


# Projects ------------------------------------------------------------------

def create_project(db: Session, user: Profile, data: ProjectCreate) -> ProjectOut:
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Name is required")
    if _name_taken(db, user.id, name):
        raise _conflict("You already have a project with this name")
    project = Project(name=name, description=data.description, created_by=user.id)
    db.add(project)
    try:
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.owner, added_by=user.id))
        _audit(db, project.id, user, "project.created", name=name)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("You already have a project with this name")
    db.refresh(project)
    return project_out(project, ProjectRole.owner)


def list_projects(db: Session, user: Profile) -> list[ProjectOut]:
    rows = db.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id, Project.archived_at.is_(None))
        .order_by(Project.created_at.desc(), Project.id.desc())
    ).all()
    return [project_out(p, role) for p, role in rows]


def update_project(db: Session, ctx: ProjectContext, data: ProjectUpdate) -> ProjectOut:
    project = ctx.project
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        name = (changes["name"] or "").strip()
        if not name:
            raise HTTPException(422, "Name is required")
        if _name_taken(db, project.created_by, name, exclude_id=project.id):
            raise _conflict("A project with this name already exists")
        changes["name"] = name
    for field, value in changes.items():
        setattr(project, field, value)
    _audit(db, project.id, ctx.user, "project.updated", **changes)
    db.commit()
    db.refresh(project)
    return project_out(project, ctx.role)


def archive_project(db: Session, ctx: ProjectContext) -> None:
    ctx.project.archived_at = datetime.now(UTC)
    _audit(db, ctx.project.id, ctx.user, "project.archived")
    db.commit()


# Members -------------------------------------------------------------------

def _member_out(m: ProjectMember) -> MemberOut:
    return MemberOut(
        user_id=m.user_id, email=m.profile.email, full_name=m.profile.full_name, role=m.role, joined_at=m.created_at
    )


def list_members(db: Session, ctx: ProjectContext) -> list[MemberOut]:
    members = db.scalars(
        select(ProjectMember)
        .join(Profile, Profile.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == ctx.project.id)
        .order_by(Profile.email)
    ).all()
    return [_member_out(m) for m in members]


def _get_member(db: Session, project_id: int, user_id: uuid.UUID) -> ProjectMember:
    member = db.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return member


def _is_last_owner(db: Session, member: ProjectMember) -> bool:
    if member.role != ProjectRole.owner:
        return False
    owners = db.scalars(
        select(ProjectMember.user_id)
        .where(ProjectMember.project_id == member.project_id, ProjectMember.role == ProjectRole.owner)
        .with_for_update()
    ).all()
    return len(owners) <= 1


def add_member(db: Session, ctx: ProjectContext, email: str, role: ProjectRole) -> MemberOut:
    profile = db.scalar(select(Profile).where(func.lower(Profile.email) == email.strip().lower()))
    if profile is None or not profile.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not add this member")
    if db.get(ProjectMember, (ctx.project.id, profile.id)) is not None:
        raise _conflict("User is already a member of this project")
    member = ProjectMember(project_id=ctx.project.id, user_id=profile.id, role=role, added_by=ctx.user.id)
    db.add(member)
    _audit(db, ctx.project.id, ctx.user, "member.added", user_id=profile.id, role=role.value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("User is already a member of this project")
    db.refresh(member)
    return _member_out(member)


def change_role(db: Session, ctx: ProjectContext, user_id: uuid.UUID, role: ProjectRole) -> MemberOut:
    member = _get_member(db, ctx.project.id, user_id)
    if member.role == role:
        return _member_out(member)
    if role != ProjectRole.owner and _is_last_owner(db, member):
        raise _conflict("A project must have at least one owner. Make another member owner first.")
    old = member.role
    member.role = role
    _audit(db, ctx.project.id, ctx.user, "member.role_changed",
           user_id=user_id, old_role=old.value, new_role=role.value)
    db.commit()
    return _member_out(member)


def oldest_other_member(db: Session, project_id: int, exclude_user_id: uuid.UUID) -> ProjectMember | None:
    """The member who joined the project first, excluding the given user."""
    return db.scalars(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id != exclude_user_id)
        .order_by(ProjectMember.created_at, ProjectMember.user_id)
        .limit(1)
    ).first()


def remove_member(db: Session, ctx: ProjectContext, user_id: uuid.UUID) -> None:
    is_self = user_id == ctx.user.id
    if not is_self and not ctx.can("members.manage"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project role")
    member = _get_member(db, ctx.project.id, user_id)
    if _is_last_owner(db, member):
        # Only the last owner can remove the last owner, so this is always the owner leaving.
        successor = oldest_other_member(db, ctx.project.id, user_id)
        if successor is None:
            raise _conflict("You are the only member of this project. Archive it instead of leaving.")
        old_role = successor.role
        successor.role = ProjectRole.owner
        _audit(db, ctx.project.id, ctx.user, "member.role_changed", user_id=successor.user_id,
               old_role=old_role.value, new_role=ProjectRole.owner.value, reason="last_owner_left")
    db.delete(member)
    _audit(db, ctx.project.id, ctx.user, "member.removed",
           user_id=user_id, role=member.role.value, self_removed=is_self)
    db.commit()
