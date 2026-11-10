"""Exact-duplicate lookup for imports (story #8 can extend this)."""
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Review

CHUNK = 500  # keeps each IN (...) list well below the database's parameter limit


def existing_hashes(db: Session, project_id: int, hashes: Iterable[str]) -> set[str]:
    """Those of `hashes` that belong to a review already saved in the project."""
    wanted = list(set(hashes))
    found: set[str] = set()
    for start in range(0, len(wanted), CHUNK):
        chunk = wanted[start : start + CHUNK]
        found.update(
            db.scalars(select(Review.content_hash).where(Review.project_id == project_id, Review.content_hash.in_(chunk)))
        )
    return found
