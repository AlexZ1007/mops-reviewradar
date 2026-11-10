"""CSV import (story #6). Reads: any member. Importing: owners and analysts (`reviews.write`).

Rows with problems are reported and skipped; the valid ones are still imported. A file that cannot
be read at all (empty, wrong encoding, no `content` column...) is rejected and nothing is saved.
"""
import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import ProjectContext
from app.imports.csv_parser import CsvFormatError, parse_csv
from app.imports.duplicates import existing_hashes
from app.imports.validation import ValidReview, validate_row
from app.models import AuditLog, Import, ImportRowError, ImportStatus, Review, ReviewSource
from app.reviews.hashing import content_hash

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_STORED_ERRORS = 500  # `invalid_rows` keeps the true count


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
    return found


def list_imports(db: Session, ctx: ProjectContext) -> list[Import]:
    return list(db.scalars(select(Import).where(Import.project_id == ctx.project.id).order_by(Import.id.desc())))


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

    run = Import(
        project_id=ctx.project.id,
        uploaded_by=ctx.user.id,
        file_name=name[:255],
        file_sha256=hashlib.sha256(raw).hexdigest(),
        status=ImportStatus.processing,
        total_rows=len(rows),
    )
    db.add(run)
    db.flush()  # gives the import its id

    errors: list[ImportRowError] = []
    invalid = 0
    candidates: list[tuple[ValidReview, str]] = []
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
        candidates.append((review, content_hash(review.content)))

    seen = existing_hashes(db, ctx.project.id, (digest for _, digest in candidates))
    new_reviews: list[Review] = []
    duplicates = 0
    for review, digest in candidates:
        if digest in seen:  # already in the project, or earlier in this same file
            duplicates += 1
            continue
        seen.add(digest)
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
    return _with_errors(db, run.id)
