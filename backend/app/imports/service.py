"""CSV import (story #6). Reads: any member. Importing: owners and analysts (`reviews.write`).

Rows with problems are reported and skipped; the valid ones are still imported. A file that cannot
be read at all (empty, wrong encoding, no `content` column...) is rejected and nothing is saved.
"""
import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import ProjectContext
from app.imports.csv_parser import CsvFormatError, parse_csv
from app.imports.duplicates import existing_review_ids
from app.imports.validation import ValidReview, validate_row
from app.models import AuditLog, Import, ImportRowError, ImportStatus, Review, ReviewSource
from app.reviews.hashing import content_hash
from app.schemas import ImportDuplicateOut

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_STORED_ERRORS = 500  # `invalid_rows` keeps the true count
MAX_REPORTED_DUPLICATES = 500  # `duplicate_rows` keeps the true count
PREVIEW_CHARS = 100


def _preview(text: str) -> str:
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + "…"


def _first_import_of(db: Session, project_id: int, sha256: str, before: int | None = None) -> int | None:
    """The id of the first import in the project of a file with this hash (older than `before`, if given)."""
    stmt = select(func.min(Import.id)).where(Import.project_id == project_id, Import.file_sha256 == sha256)
    if before is not None:
        stmt = stmt.where(Import.id < before)
    return db.scalar(stmt)


def _audit(db: Session, ctx: ProjectContext, action: str, import_id: int, **details) -> None:
    db.add(
        AuditLog(
            project_id=ctx.project.id,
            actor_id=ctx.user.id,
            action=action,
            target_type="import",
            target_id=import_id,
            details=details or None,
        )
    )


def _with_errors(db: Session, import_id: int) -> Import | None:
    """The import with its row errors already loaded (the session is closed before the response is built)."""
    stmt = select(Import).options(selectinload(Import.errors)).where(Import.id == import_id)
    return db.scalar(stmt.execution_options(populate_existing=True))


def get_import(db: Session, ctx: ProjectContext, import_id: int) -> Import:
    found = _with_errors(db, import_id)
    # An import of another project is reported as missing, never as forbidden.
    if found is None or found.project_id != ctx.project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found")
    found.repeat_of = _first_import_of(db, ctx.project.id, found.file_sha256, before=found.id)
    return found


def list_imports(db: Session, ctx: ProjectContext) -> list[Import]:
    """Newest first. Each import says whether an older one holds the very same file."""
    imports = list(db.scalars(select(Import).where(Import.project_id == ctx.project.id).order_by(Import.id.desc())))
    first: dict[str, int] = {}
    for item in reversed(imports):  # oldest first
        first.setdefault(item.file_sha256, item.id)
        item.repeat_of = None if first[item.file_sha256] == item.id else first[item.file_sha256]
    return imports


def run_import(db: Session, ctx: ProjectContext, file_name: str, raw: bytes) -> Import:
    name = file_name.replace("\\", "/").rsplit("/", 1)[-1].strip()  # some clients send a full path
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"The file is larger than {MAX_FILE_BYTES // 2**20} MB")
    if not name.lower().endswith(".csv"):
        raise HTTPException(422, "Please upload a .csv file")
    try:
        rows = parse_csv(raw)
    except CsvFormatError as e:
        raise HTTPException(422, str(e))

    sha256 = hashlib.sha256(raw).hexdigest()
    repeat_of = _first_import_of(db, ctx.project.id, sha256)  # looked up before this import exists
    run = Import(
        project_id=ctx.project.id,
        uploaded_by=ctx.user.id,
        file_name=name[:255],
        file_sha256=sha256,
        status=ImportStatus.processing,
        total_rows=len(rows),
    )
    db.add(run)
    db.flush()  # gives the import its id

    errors: list[ImportRowError] = []
    invalid = 0
    candidates: list[tuple[int, ValidReview, str]] = []  # (row number, review, content hash)
    for row in rows:
        review, issues = validate_row(row)
        if review is None:
            invalid += 1
            for issue in issues:
                if len(errors) < MAX_STORED_ERRORS:
                    errors.append(
                        ImportRowError(import_id=run.id, row_number=row.row_number, field=issue.field, message=issue.message)
                    )
            continue
        candidates.append((row.row_number, review, content_hash(review.content)))

    saved = existing_review_ids(db, ctx.project.id, (digest for _, _, digest in candidates))
    first_row: dict[str, int] = {}  # hash -> row of its first appearance in this file
    new_reviews: list[Review] = []
    duplicates = 0
    duplicate_report: list[ImportDuplicateOut] = []
    for number, review, digest in candidates:
        of_review_id = saved.get(digest)  # already saved in the project...
        if of_review_id is not None or digest in first_row:  # ...or earlier in this same file
            duplicates += 1
            if len(duplicate_report) < MAX_REPORTED_DUPLICATES:
                duplicate_report.append(
                    ImportDuplicateOut(
                        row_number=number,
                        content=_preview(review.content),
                        of_review_id=of_review_id,
                        of_row=None if of_review_id is not None else first_row[digest],
                    )
                )
            continue
        first_row[digest] = number
        new_reviews.append(
            Review(
                project_id=ctx.project.id,
                import_id=run.id,
                created_by=ctx.user.id,
                source=ReviewSource.csv,
                external_id=review.external_id,
                author=review.author,
                rating=review.rating,
                content=review.content,
                content_hash=digest,
                reviewed_at=review.reviewed_at,
            )
        )

    run.imported_rows = len(new_reviews)
    run.duplicate_rows = duplicates
    run.invalid_rows = invalid
    run.status = ImportStatus.completed
    run.finished_at = datetime.now(UTC)
    db.add_all(errors + new_reviews)
    try:
        db.flush()
        _audit(
            db, ctx, "import.completed", run.id,
            file_name=run.file_name, total_rows=run.total_rows, imported_rows=run.imported_rows,
            duplicate_rows=run.duplicate_rows, invalid_rows=run.invalid_rows,
        )
        db.commit()
    except IntegrityError:  # someone saved one of these reviews while we were working
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "The project changed during the import. Please try again.")
    result = _with_errors(db, run.id)
    result.repeat_of = repeat_of
    result.duplicates = duplicate_report  # not stored: only the counts are kept in the history
    return result
