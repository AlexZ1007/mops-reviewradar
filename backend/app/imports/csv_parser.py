"""Reads an uploaded CSV file into rows.

Knows nothing about the database or about what makes a review valid: it only deals with the
shape of the file (encoding, delimiter, header, quoting).
"""
import csv
import io
from dataclasses import dataclass

# Header name (lower case, spaces -> "_") -> the column name used from here on.
ALIASES = {
    "content": "content", "review": "content", "text": "content", "comment": "content",
    "rating": "rating", "stars": "rating",
    "author": "author", "user": "author",
    "date": "date", "reviewed_at": "date",
    "external_id": "external_id", "id": "external_id",
}
DELIMITERS = (",", ";", "\t")  # Excel in many locales (e.g. Romanian) writes ";"
MAX_ROWS = 10_000  # the import runs inside one request


class CsvFormatError(ValueError):
    """The file as a whole cannot be used (as opposed to one bad row, which is reported per row)."""


@dataclass(frozen=True)
class CsvRow:
    row_number: int  # as in a spreadsheet: the header is row 1, the first review row 2
    values: dict[str, str]  # column name -> trimmed text; columns missing from a short row are left out
    extra_cells: int = 0  # filled cells beyond the header's columns: usually an unquoted comma in the text


def _column(header: str) -> str | None:
    return ALIASES.get("_".join(header.strip().lower().split()))


def _read_header(record: list[str]) -> list[str | None]:
    columns = [_column(name) for name in record]
    for column in {c for c in columns if c}:
        names = [name.strip() for name, c in zip(record, columns) if c == column]
        if len(names) > 1:
            raise CsvFormatError(f"The '{column}' column appears twice ({', '.join(names)}). Keep only one.")
    if "content" not in columns:
        found = ", ".join(name.strip() for name in record if name.strip())
        raise CsvFormatError(
            f"The file has no 'content' column (also accepted: review, text, comment). Columns found: {found}"
        )
    return columns


def parse_csv(raw: bytes) -> list[CsvRow]:
    try:
        text = raw.decode("utf-8-sig")  # also drops the BOM that Excel adds
    except UnicodeDecodeError:
        raise CsvFormatError("The file is not UTF-8 encoded. In Excel use Save As > CSV UTF-8.")
    if not text.strip():
        raise CsvFormatError("The file is empty")

    first_line = next(line for line in text.splitlines() if line.strip())
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=max(DELIMITERS, key=first_line.count))

    header: list[str | None] | None = None
    rows: list[CsvRow] = []
    number = 0
    try:
        for number, record in enumerate(reader, start=1):
            if not any(cell.strip() for cell in record):
                continue  # blank line or a row of empty cells (still counted in the numbering)
            if header is None:
                header = _read_header(record)
                continue
            values = {column: cell.strip() for column, cell in zip(header, record) if column}
            extra = sum(1 for cell in record[len(header):] if cell.strip())  # trailing empty cells do not count
            rows.append(CsvRow(row_number=number, values=values, extra_cells=extra))
            if len(rows) > MAX_ROWS:
                raise CsvFormatError(f"The file has more than {MAX_ROWS:,} rows. Split it into smaller files.")
    except csv.Error as e:
        problem = "has a field that is too large" if "field larger" in str(e) else f"could not be read ({e})"
        raise CsvFormatError(f"Row {number + 1} {problem}")

    if header is None:
        raise CsvFormatError("The file is empty")
    if not rows:
        raise CsvFormatError("The file has no review rows, only the header")
    return rows
