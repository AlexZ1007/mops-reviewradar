"""Reviews of a project. Reads: any member. Writes: owners and analysts (`reviews.write`)."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext
from app.models import AuditLog, Category, Review, ReviewSource
from app.reviews.hashing import content_hash
from app.schemas import ReviewCreate

DUPLICATE = "A review with the same content already exists in this project"


def _audit(db: Session, ctx: ProjectContext, action: str, review_id: int, **details) -> None:
    db.add(
        AuditLog(
            project_id=ctx.project.id,
            actor_id=ctx.user.id,
            action=action,
            target_type="review",
            target_id=review_id,
            details=details or None,
        )
    )


def is_duplicate(db: Session, project_id: int, digest: str) -> bool:
    """Is there already a review with this content hash in the project?"""
    return db.scalar(select(Review.id).where(Review.project_id == project_id, Review.content_hash == digest)) is not None


def list_reviews(db: Session, ctx: ProjectContext, limit: int = 50, offset: int = 0) -> list[Review]:
    """Newest first. Minimal on purpose: searching and filtering belong to the review-list story."""
    stmt = select(Review).where(Review.project_id == ctx.project.id).order_by(Review.id.desc())
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def create_manual_review(db: Session, ctx: ProjectContext, data: ReviewCreate) -> Review:
    if data.category_id is not None:
        category = db.get(Category, data.category_id)
        # A category of another project is reported as missing, never revealed.
        if category is None or category.project_id != ctx.project.id:
            raise HTTPException(422, "Category not found in this project")

    digest = content_hash(data.content)
    if is_duplicate(db, ctx.project.id, digest):
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)

    review = Review(
        project_id=ctx.project.id,
        category_id=data.category_id,
        created_by=ctx.user.id,
        source=ReviewSource.manual,
        author=data.author,
        rating=data.rating,
        content=data.content,
        content_hash=digest,
        reviewed_at=data.reviewed_at,
    )
    db.add(review)
    try:
        db.flush()
        _audit(db, ctx, "review.created", review.id, source=ReviewSource.manual.value)
        db.commit()
    except IntegrityError:  # lost a race against the unique (project_id, content_hash) constraint
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE)
    db.refresh(review)
    return review
