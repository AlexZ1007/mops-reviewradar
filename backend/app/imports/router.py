from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import ProjectContext, require_permission
from app.db import get_db
from app.imports import service
from app.schemas import ImportDetailOut, ImportOut

router = APIRouter(prefix="/projects/{project_id}/imports", tags=["imports"])


@router.get("", response_model=list[ImportOut])
def list_imports(
    ctx: ProjectContext = Depends(require_permission("project.read")),
    db: Session = Depends(get_db),
):
    return service.list_imports(db, ctx)


@router.post("", response_model=ImportDetailOut, status_code=status.HTTP_201_CREATED)
def import_csv(
    file: UploadFile = File(description="A UTF-8 .csv file with a header row"),
    ctx: ProjectContext = Depends(require_permission("reviews.write")),
    db: Session = Depends(get_db),
):
    raw = file.file.read(service.MAX_FILE_BYTES + 1)  # one byte more than allowed is enough to notice it is too big
    return service.run_import(db, ctx, file.filename or "", raw)


@router.get("/{import_id}", response_model=ImportDetailOut)
def get_import(
    import_id: int,
    ctx: ProjectContext = Depends(require_permission("project.read")),
    db: Session = Depends(get_db),
):
    return service.get_import(db, ctx, import_id)
