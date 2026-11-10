"""Checks one CSV row and turns it into a review.

All the row rules live here, in one place, so that they are easy to extend (story #7).
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.imports.csv_parser import CsvRow
from app.schemas import MAX_REVIEW_LENGTH, MAX_TEXT_FIELD


@dataclass(frozen=True)
class RowIssue:
    field: str  # CSV column name
    message: str


@dataclass(frozen=True)
class ValidReview:
    content: str
    rating: int | None
    author: str | None
    reviewed_at: datetime | None
    external_id: str | None


def _rating(value: str, issues: list[RowIssue]) -> int | None:
    if not value:
        return None
    try:
        number = Decimal(value)
        ok = number == number.to_integral_value() and 1 <= number <= 5
    except InvalidOperation:
        ok = False
    if not ok:
        issues.append(RowIssue("rating", "Rating must be a whole number from 1 to 5"))
        return None
    return int(number)


def _date(value: str, issues: list[RowIssue]) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        issues.append(RowIssue("date", "Date must look like 2026-11-01 (or 2026-11-01T10:30:00)"))
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)  # no time zone means UTC


def validate_row(row: CsvRow) -> tuple[ValidReview | None, list[RowIssue]]:
    """Returns the review, or `None` and every problem found in the row."""
    values = {column: cell.strip() for column, cell in row.values.items()}
    issues: list[RowIssue] = []

    content = values.get("content", "")
    if not content:
        issues.append(RowIssue("content", "Content is required"))
    elif len(content) > MAX_REVIEW_LENGTH:
        issues.append(RowIssue("content", f"Content is longer than {MAX_REVIEW_LENGTH} characters"))

    rating = _rating(values.get("rating", ""), issues)
    reviewed_at = _date(values.get("date", ""), issues)

    for field in ("author", "external_id"):
        if len(values.get(field, "")) > MAX_TEXT_FIELD:
            issues.append(RowIssue(field, f"The {field.replace('_', ' ')} is longer than {MAX_TEXT_FIELD} characters"))

    if issues:
        return None, issues
    return ValidReview(content, rating, values.get("author") or None, reviewed_at, values.get("external_id") or None), []
