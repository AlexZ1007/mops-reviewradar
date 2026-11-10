"""Story #6: turning an uploaded CSV file into rows, and checking each row. Pure functions, no database."""
from datetime import UTC, datetime

import pytest

from app.imports.csv_parser import CsvFormatError, CsvRow, parse_csv
from app.imports.validation import validate_row


def parse(text: str, encoding: str = "utf-8"):
    return parse_csv(text.encode(encoding))


# Parsing ---------------------------------------------------------------------------------

def test_parse_basic_file():
    rows = parse("content,rating,author,date,external_id\nGreat app,5,Maria,2026-11-01,r-1\nSlow,2,Ion,2026-11-02,r-2\n")
    assert [r.row_number for r in rows] == [2, 3]  # spreadsheet numbering: the header is row 1
    assert rows[0].values == {
        "content": "Great app", "rating": "5", "author": "Maria", "date": "2026-11-01", "external_id": "r-1",
    }
    assert rows[1].values["content"] == "Slow"


def test_only_columns_present_in_the_file_are_returned():
    rows = parse("content,rating\nGreat,5\n")
    assert rows[0].values == {"content": "Great", "rating": "5"}


def test_headers_ignore_case_spaces_and_accept_aliases():
    rows = parse("Review, Stars ,User,Date,ID\nGreat,5,Maria,2026-11-01,r-1\n")
    assert rows[0].values == {
        "content": "Great", "rating": "5", "author": "Maria", "date": "2026-11-01", "external_id": "r-1",
    }
    assert parse("External ID,Text\nr-1,Hello\n")[0].values == {"external_id": "r-1", "content": "Hello"}


def test_unknown_columns_are_ignored():
    assert parse("content,device,os\nGreat,phone,android\n")[0].values == {"content": "Great"}


def test_values_are_trimmed():
    assert parse("content,author\n  Great app  ,  Maria \n")[0].values == {"content": "Great app", "author": "Maria"}


def test_utf8_bom_is_accepted():
    assert parse("﻿content\nGreat\n")[0].values == {"content": "Great"}


def test_diacritics_survive():
    assert parse('content\n"Foarte bună, mulțumesc!"\n')[0].values["content"] == "Foarte bună, mulțumesc!"


@pytest.mark.parametrize("delimiter", [";", "\t"])
def test_other_delimiters_are_detected(delimiter):
    rows = parse(f"content{delimiter}rating\nGreat{delimiter}5\n")
    assert rows[0].values == {"content": "Great", "rating": "5"}


def test_quoted_fields_with_commas_quotes_and_newlines():
    rows = parse('content,rating\n"Good, but ""slow""\nand buggy",3\nNext,4\n')
    assert rows[0].values["content"] == 'Good, but "slow"\nand buggy'
    assert (rows[0].row_number, rows[1].row_number) == (2, 3)  # a multi-line field is still one row


def test_windows_line_endings():
    assert [r.values["content"] for r in parse("content\r\nOne\r\nTwo\r\n")] == ["One", "Two"]


def test_blank_rows_are_skipped_but_numbering_is_kept():
    rows = parse("content,rating\nOne,1\n\n,\nTwo,2\n")
    assert [(r.row_number, r.values["content"]) for r in rows] == [(2, "One"), (5, "Two")]


def test_short_rows_leave_missing_cells_out():
    assert parse("content,rating,author\nGreat\n")[0].values.get("rating", "") == ""


def test_missing_content_column():
    with pytest.raises(CsvFormatError, match="content"):
        parse("rating,author\n5,Maria\n")


def test_content_given_twice():
    with pytest.raises(CsvFormatError, match="twice"):
        parse("content,review\nA,B\n")


@pytest.mark.parametrize("text", ["", "   \n\n", ",,,\n,\n"])
def test_empty_file(text):
    with pytest.raises(CsvFormatError, match="empty"):
        parse(text)


def test_header_without_reviews():
    with pytest.raises(CsvFormatError, match="no review"):
        parse("content,rating\n")
    with pytest.raises(CsvFormatError, match="no review"):
        parse("content,rating\n\n,\n")


def test_not_utf8():
    with pytest.raises(CsvFormatError, match="UTF-8"):
        parse("content\nfoarte bună\n", encoding="cp1250")


def test_field_too_large():
    with pytest.raises(CsvFormatError, match="too large"):
        parse("content\n" + "x" * 200_000 + "\n")


# Row validation ----------------------------------------------------------------------------

def row(**values) -> CsvRow:
    return CsvRow(row_number=2, values=values)


def test_valid_row():
    review, issues = validate_row(
        row(content="Great app", rating="5", author="Maria", date="2026-11-01", external_id="r-1")
    )
    assert issues == []
    assert (review.content, review.rating, review.author, review.external_id) == ("Great app", 5, "Maria", "r-1")
    assert review.reviewed_at == datetime(2026, 11, 1, tzinfo=UTC)


def test_only_content_is_required():
    review, issues = validate_row(row(content="Great"))
    assert issues == []
    assert (review.rating, review.author, review.reviewed_at, review.external_id) == (None, None, None, None)


def test_blank_optional_cells_become_none():
    review, issues = validate_row(row(content="Great", rating="", author="", date="", external_id=""))
    assert issues == [] and review.rating is None and review.author is None


@pytest.mark.parametrize("content", ["", "   "])
def test_content_is_required(content):
    review, issues = validate_row(row(content=content))
    assert review is None
    assert [i.field for i in issues] == ["content"]


def test_content_too_long():
    assert validate_row(row(content="x" * 10_000))[1] == []
    review, issues = validate_row(row(content="x" * 10_001))
    assert review is None and [i.field for i in issues] == ["content"]


@pytest.mark.parametrize("value,expected", [("1", 1), ("5", 5), ("4.0", 4), (" 3 ", 3)])
def test_valid_ratings(value, expected):
    review, issues = validate_row(row(content="x", rating=value))
    assert issues == [] and review.rating == expected


@pytest.mark.parametrize("value", ["0", "6", "-1", "4.5", "abc", "five", "1e3"])
def test_invalid_ratings(value):
    review, issues = validate_row(row(content="x", rating=value))
    assert review is None and [i.field for i in issues] == ["rating"]


def test_date_formats():
    assert validate_row(row(content="x", date="2026-11-01T10:30:00+02:00"))[0].reviewed_at.utcoffset().total_seconds() == 7200
    assert validate_row(row(content="x", date="2026-11-01T10:30:00"))[0].reviewed_at.tzinfo is UTC  # naive means UTC


@pytest.mark.parametrize("value", ["yesterday", "01/11/2026", "2026-13-45"])
def test_invalid_dates(value):
    review, issues = validate_row(row(content="x", date=value))
    assert review is None and [i.field for i in issues] == ["date"]


def test_author_and_external_id_length_limits():
    assert validate_row(row(content="x", author="a" * 120, external_id="e" * 120))[1] == []
    _, issues = validate_row(row(content="x", author="a" * 121, external_id="e" * 121))
    assert [i.field for i in issues] == ["author", "external_id"]


def test_all_problems_of_a_row_are_reported_together():
    review, issues = validate_row(row(content="", rating="9", date="nope"))
    assert review is None
    assert [i.field for i in issues] == ["content", "rating", "date"]
    assert all(i.message for i in issues)
