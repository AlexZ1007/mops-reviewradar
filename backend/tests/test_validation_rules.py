"""Story #7: stricter checks on imported rows, clearer messages and a downloadable error report."""
import csv
import io
from datetime import UTC, datetime, timedelta

import pytest

from app.imports.csv_parser import MAX_ROWS, CsvFormatError, CsvRow, parse_csv
from app.imports.reports import errors_csv, safe_cell
from app.imports.validation import validate_row
from app.models import ImportRowError


def issues_for(**values):
    return validate_row(CsvRow(row_number=2, values=values))[1]


# Messages --------------------------------------------------------------------------------------

def test_messages_quote_the_offending_value():
    by_field = {i.field: i.message for i in issues_for(content="ok", rating="9", date="nope")}
    assert "'9'" in by_field["rating"]
    assert "'nope'" in by_field["date"]


def test_long_values_are_shortened_in_messages():
    message = issues_for(content="ok", rating="9" * 200)[0].message
    assert len(message) < 120 and "…" in message


# Content ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("content", ["---", "???", "...", "  - * ", "😀😀"])
def test_content_needs_a_letter_or_digit(content):
    assert [i.field for i in issues_for(content=content)] == ["content"]


@pytest.mark.parametrize("content", ["5", "ok", "Foarte bună", "Очень хорошо"])
def test_content_with_letters_or_digits_is_fine(content):
    assert issues_for(content=content) == []


# Dates -----------------------------------------------------------------------------------------

def test_future_dates_are_rejected():
    future = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()
    assert [i.field for i in issues_for(content="x", date=future)] == ["date"]


def test_today_is_fine():
    assert issues_for(content="x", date=datetime.now(UTC).date().isoformat()) == []


def test_implausibly_old_dates_are_rejected():
    assert [i.field for i in issues_for(content="x", date="1989-12-31")] == ["date"]
    assert issues_for(content="x", date="1990-01-01") == []


# Columns that do not line up -----------------------------------------------------------------------

def test_unquoted_comma_is_explained():
    rows = parse_csv(b"content,rating\nGreat, but slow,4\n")
    assert rows[0].extra_cells == 1
    review, issues = validate_row(rows[0])
    assert review is None
    assert issues[0].field == "row" and "quotes" in issues[0].message


def test_empty_trailing_cells_are_ignored():
    rows = parse_csv(b"content,rating\nGreat,4,,\n")
    assert rows[0].extra_cells == 0
    assert validate_row(rows[0])[1] == []


def test_rows_built_by_hand_have_no_extra_cells():
    assert CsvRow(row_number=2, values={"content": "x"}).extra_cells == 0


# File size ---------------------------------------------------------------------------------------

def test_row_limit():
    body = "content\n" + "\n".join(f"review {i}" for i in range(MAX_ROWS)) + "\n"
    assert len(parse_csv(body.encode())) == MAX_ROWS
    with pytest.raises(CsvFormatError, match="10,000"):
        parse_csv((body + "one more\n").encode())


# Error report -----------------------------------------------------------------------------------

def test_safe_cell_neutralises_formulas():
    for value in ["=1+1", "+1", "-1", "@SUM(A1)", "\t=1", "\r=1"]:
        assert safe_cell(value).startswith("'"), value
    assert safe_cell("Rating '9' is not valid") == "Rating '9' is not valid"
    assert safe_cell("") == ""


def test_errors_csv_has_bom_header_and_rows():
    data = errors_csv([
        ImportRowError(row_number=3, field="rating", message='Bad, "quoted"'),
        ImportRowError(row_number=4, field=None, message="Oops"),
    ])
    assert data.startswith(b"\xef\xbb\xbf")  # lets Excel read the UTF-8 text
    table = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert table == [["row", "column", "problem"], ["3", "rating", 'Bad, "quoted"'], ["4", "", "Oops"]]


def test_errors_csv_without_errors_is_only_the_header():
    table = list(csv.reader(io.StringIO(errors_csv([]).decode("utf-8-sig"))))
    assert table == [["row", "column", "problem"]]


# Through the API --------------------------------------------------------------------------------------

@pytest.fixture
def owner(make_user):
    return make_user("owner@x.io")


@pytest.fixture
def project(client, owner, auth):
    r = client.post("/projects", json={"name": "App"}, headers=auth(owner))
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def url(project):
    return f"/projects/{project['id']}/imports"


@pytest.fixture
def member(client, make_user, auth, owner, project):
    def _member(email, role):
        user = make_user(email)
        r = client.post(
            f"/projects/{project['id']}/invitations", json={"email": email, "role": role}, headers=auth(owner)
        )
        assert client.post(f"/invitations/{r.json()['id']}/accept", headers=auth(user)).status_code == 200
        return user

    return _member


@pytest.fixture
def upload(client, owner, auth, url):
    def _upload(content, *, user=None, name="reviews.csv"):
        return client.post(url, files={"file": (name, content.encode(), "text/csv")}, headers=auth(user or owner))

    return _upload


def test_comma_mistake_is_reported_for_the_row(upload):
    body = upload("content,rating\nGreat, but slow,4\nFine,5\n").json()
    assert (body["imported_rows"], body["invalid_rows"]) == (1, 1)
    first = body["errors"][0]
    assert (first["row_number"], first["field"]) == (2, "row") and "quotes" in first["message"]


def test_too_many_rows_rejects_the_file(upload):
    r = upload("content\n" + "\n".join(f"r{i}" for i in range(MAX_ROWS + 1)))
    assert r.status_code == 422 and "10,000" in r.json()["detail"]


@pytest.fixture
def report(client, auth, url):
    return lambda import_id, user: client.get(f"{url}/{import_id}/errors.csv", headers=auth(user))


def test_download_problems_as_csv(upload, report, owner):
    import_id = upload("content,rating\nGreat,5\n,3\nSlow,9\n").json()["id"]
    r = report(import_id, owner)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == f'attachment; filename="import-{import_id}-problems.csv"'
    table = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert table[0] == ["row", "column", "problem"]
    assert [(row[0], row[1]) for row in table[1:]] == [("3", "content"), ("4", "rating")]


def test_download_when_nothing_failed(upload, report, owner):
    import_id = upload("content\nGreat\n").json()["id"]
    r = report(import_id, owner)
    assert r.status_code == 200 and len(list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))) == 1


def test_viewer_can_download_the_report(upload, report, member):
    import_id = upload("content,rating\n,3\n").json()["id"]
    assert report(import_id, member("viewer@x.io", "viewer")).status_code == 200


def test_report_of_unknown_import_404(report, owner):
    assert report(999, owner).status_code == 404


def test_report_of_another_projects_import_404(client, upload, owner, auth):
    import_id = upload("content,rating\n,3\n").json()["id"]
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    r = client.get(f"/projects/{other['id']}/imports/{import_id}/errors.csv", headers=auth(owner))
    assert r.status_code == 404


def test_report_hidden_from_non_members(upload, report, make_user):
    import_id = upload("content,rating\n,3\n").json()["id"]
    assert report(import_id, make_user("stranger@x.io")).status_code == 404


def test_report_requires_authentication(client, upload, url):
    import_id = upload("content,rating\n,3\n").json()["id"]
    assert client.get(f"{url}/{import_id}/errors.csv").status_code == 401
