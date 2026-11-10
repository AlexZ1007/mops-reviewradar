"""The error report of an import, as a CSV file the user can fix and upload again."""
import csv
import io
from collections.abc import Iterable

from app.models import ImportRowError

FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: str) -> str:
    """Spreadsheets run text that starts with = + - or @ as a formula: an apostrophe in front stops that."""
    return "'" + value if value.startswith(FORMULA_STARTS) else value


def errors_csv(errors: Iterable[ImportRowError]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["row", "column", "problem"])
    for error in errors:
        writer.writerow([error.row_number, safe_cell(error.field or ""), safe_cell(error.message)])
    return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8")  # the BOM lets Excel read the text as UTF-8
