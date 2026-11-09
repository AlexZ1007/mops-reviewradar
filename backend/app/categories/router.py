from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext, require_permission
from app.categories import service
from app.db import get_db
from app.schemas import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/projects/{project_id}/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(
    q: str | None = Query(default=None, max_length=80, description="Case-insensitive name filter"),
    ctx: ProjectContext = Depends(require_permission("project.read")),
    db: Session = Depends(get_db),
):
    return service.list_categories(db, ctx, q)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    ctx: ProjectContext = Depends(require_permission("categories.manage")),
    db: Session = Depends(get_db),
):
    return service.create_category(db, ctx, data)


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: int,
    ctx: ProjectContext = Depends(require_permission("project.read")),
    db: Session = Depends(get_db),
):
    return service.get_category(db, ctx, category_id)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    ctx: ProjectContext = Depends(require_permission("categories.manage")),
    db: Session = Depends(get_db),
):
    return service.update_category(db, ctx, category_id, data)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    ctx: ProjectContext = Depends(require_permission("categories.manage")),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_category(db, ctx, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
