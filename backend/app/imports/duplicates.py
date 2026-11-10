"""Exact-duplicate lookup for imports (story #8)."""
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Review

CHUNK = 500  # keeps each IN (...) list well below the database's parameter limit


def existing_review_ids(db: Session, project_id: int, hashes: Iterable[str]) -> dict[str, int]:
    """For those of `hashes` that belong to a review already saved in the project: hash -> review id."""
    wanted = list(set(hashes))
    found: dict[str, int] = {}
    for start in range(0, len(wanted), CHUNK):
        chunk = wanted[start : start + CHUNK]
        rows = db.execute(
            select(Review.content_hash, Review.id).where(Review.project_id == project_id, Review.content_hash.in_(chunk))
        )
        found.update({digest: review_id for digest, review_id in rows})
    return found
