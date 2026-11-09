"""Custom feedback categories per project (story #4). Reads: any member. Writes: owners (`categories.manage`)."""
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext
from app.models import AuditLog, Category
from app.schemas import CategoryCreate, CategoryUpdate

DUPLICATE = "This project already has a category with that name"


def _audit(db: Session, ctx: ProjectContext, action: str, category_id: int, **details) -> None:
    db.add(
        AuditLog(
            project_id=ctx.project.id,
            actor_id=ctx.user.id,
            action=action,
            target_type="category",
            target_id=category_id,
            details=details or None,
        )
    )


def _name_taken(db: Session, project_id: int, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(Category.id).where(Category.project_id == project_id, func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    return db.scalar(stmt.limit(1)) is not None


def get_category(db: Session, ctx: ProjectContext, category_id: int) -> Category:
    category = db.get(Category, category_id)
    # A category of another project is reported as missing, never as forbidden.
    if category is None or category.project_id != ctx.project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


def list_categories(db: Session, ctx: ProjectContext, q: str | None = None) -> list[Category]:
    """Categories of the project ordered by name; `q` keeps those whose name contains it (case-insensitive)."""
    stmt = select(Category).where(Category.project_id == ctx.project.id)
    term = (q or "").strip().lower()
    if term:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(func.lower(Category.name).like(f"%{escaped}%", escape="\\"))
    return list(db.scalars(stmt.order_by(func.lower(Category.name), Category.id)))


def create_category(db: Session, ctx: ProjectContext, data: CategoryCreate) -> Category:
    if _name_taken(db, ctx.project.id, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)
    category = Category(project_id=ctx.project.id, name=data.name, color=data.color)
    db.add(category)
    try:
        db.flush()
        _audit(db, ctx, "category.created", category.id, name=category.name, color=category.color)
        db.commit()
    except IntegrityError:  # lost a race against the unique index
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)
    db.refresh(category)
    return category


def update_category(db: Session, ctx: ProjectContext, category_id: int, data: CategoryUpdate) -> Category:
    category = get_category(db, ctx, category_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and _name_taken(db, ctx.project.id, changes["name"], exclude_id=category.id):
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)
    for field, value in changes.items():
        setattr(category, field, value)
    try:
        _audit(db, ctx, "category.updated", category.id, **changes)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)
    db.refresh(category)
    return category


def delete_category(db: Session, ctx: ProjectContext, category_id: int) -> None:
    category = get_category(db, ctx, category_id)
    # reviews.category_id is ON DELETE SET NULL: tagged reviews become uncategorized.
    _audit(db, ctx, "category.deleted", category.id, name=category.name)
    db.delete(category)
    db.commit()
