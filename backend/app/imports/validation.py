"""Checks one CSV row and turns it into a review.

All the row rules live here, in one place, so that they are easy to extend (story #7).
Every message names the value that was rejected, so the user can find it in the file.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.imports.csv_parser import CsvRow
from app.schemas import MAX_REVIEW_LENGTH, MAX_TEXT_FIELD

MIN_DATE = datetime(1990, 1, 1, tzinfo=UTC)  # older than this is surely a typo
SHOWN_CHARS = 40


@dataclass(frozen=True)
class RowIssue:
    field: str  # CSV column name, or "row" for a problem with the row as a whole
    message: str


@dataclass(frozen=True)
class ValidReview:
    content: str
    rating: int | None
    author: str | None
    reviewed_at: datetime | None
    external_id: str | None


def _shown(value: str) -> str:
    """The value as quoted in a message, shortened if it is long."""
    return f"'{value if len(value) <= SHOWN_CHARS else value[:SHOWN_CHARS] + '…'}'"


def _rating(value: str, issues: list[RowIssue]) -> int | None:
    if not value:
        return None
    try:
        number = Decimal(value)
        ok = number == number.to_integral_value() and 1 <= number <= 5
    except InvalidOperation:
        ok = False
    if not ok:
        issues.append(RowIssue("rating", f"Rating {_shown(value)} is not valid: use a whole number from 1 to 5"))
        return None
    return int(number)


def _date(value: str, issues: list[RowIssue]) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        issues.append(
            RowIssue("date", f"Date {_shown(value)} is not valid: use a format like 2026-11-01 (or 2026-11-01T10:30:00)")
        )
        return None
    parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)  # no time zone means UTC
    if parsed > datetime.now(UTC) + timedelta(days=1):  # a day of slack for time zones
        issues.append(RowIssue("date", f"Date {_shown(value)} is in the future"))
        return None
    if parsed < MIN_DATE:
        issues.append(RowIssue("date", f"Date {_shown(value)} is before 1990, which is unlikely to be right"))
        return None
    return parsed


def validate_row(row: CsvRow) -> tuple[ValidReview | None, list[RowIssue]]:
    """Returns the review, or `None` and every problem found in the row."""
    values = {column: cell.strip() for column, cell in row.values.items()}
    issues: list[RowIssue] = []

    if row.extra_cells:
        n = row.extra_cells
        issues.append(
            RowIssue(
                "row",
                f"This row has {n} more filled cell{'s' if n != 1 else ''} than the header has columns. "
                "If the text contains commas, wrap it in double quotes.",
            )
        )

    content = values.get("content", "")
    if not content:
        issues.append(RowIssue("content", "Content is required"))
    elif len(content) > MAX_REVIEW_LENGTH:
        issues.append(RowIssue("content", f"Content is longer than {MAX_REVIEW_LENGTH} characters"))
    elif not any(ch.isalnum() for ch in content):
        issues.append(RowIssue("content", f"Content {_shown(content)} has no letters or digits"))

    rating = _rating(values.get("rating", ""), issues)
    reviewed_at = _date(values.get("date", ""), issues)

    for field in ("author", "external_id"):
        if len(values.get(field, "")) > MAX_TEXT_FIELD:
            issues.append(RowIssue(field, f"The {field.replace('_', ' ')} is longer than {MAX_TEXT_FIELD} characters"))

    if issues:
        return None, issues
    return ValidReview(content, rating, values.get("author") or None, reviewed_at, values.get("external_id") or None), []
