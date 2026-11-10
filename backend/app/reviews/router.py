from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext, require_permission
from app.db import get_db
from app.reviews import service
from app.schemas import ReviewCreate, ReviewOut

router = APIRouter(prefix="/projects/{project_id}/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: ProjectContext = Depends(require_permission("project.read")),
    db: Session = Depends(get_db),
):
    return service.list_reviews(db, ctx, limit, offset)


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    data: ReviewCreate,
    ctx: ProjectContext = Depends(require_permission("reviews.write")),
    db: Session = Depends(get_db),
):
    return service.create_manual_review(db, ctx, data)
