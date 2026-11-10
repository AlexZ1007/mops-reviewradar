"""Story #6: owners and analysts import reviews from a CSV file."""
import hashlib

import pytest
from sqlalchemy import inspect, select

from app.imports import service as import_service
from app.imports.service import MAX_FILE_BYTES, MAX_STORED_ERRORS
from app.models import AuditLog, Import, Review, ReviewSource
from app.reviews.hashing import content_hash

GOOD = "content,rating,author,date\nGreat app,5,Maria,2026-11-01\nToo slow,2,Ion,2026-11-02\nNice,4,,\n"


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
    """A user who joined `project` with the given role (invite, then accept)."""

    def _member(email, role):
        user = make_user(email)
        r = client.post(
            f"/projects/{project['id']}/invitations", json={"email": email, "role": role}, headers=auth(owner)
        )
        assert r.status_code == 201
        assert client.post(f"/invitations/{r.json()['id']}/accept", headers=auth(user)).status_code == 200
        return user

    return _member


@pytest.fixture
def upload(client, owner, auth, url):
    def _upload(content=GOOD, *, name="reviews.csv", user=None, target=None):
        data = content if isinstance(content, bytes) else content.encode("utf-8")
        return client.post(
            target or url, files={"file": (name, data, "text/csv")}, headers=auth(user or owner)
        )

    return _upload


# Happy path ----------------------------------------------------------------------------------

def test_import_valid_file(upload, project, owner, db):
    r = upload()
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "completed"
    assert (body["total_rows"], body["imported_rows"], body["duplicate_rows"], body["invalid_rows"]) == (3, 3, 0, 0)
    assert body["errors"] == []
    assert body["file_name"] == "reviews.csv"
    assert body["project_id"] == project["id"] and body["uploaded_by"] == str(owner.id)
    assert body["finished_at"] is not None

    reviews = db.scalars(select(Review).where(Review.project_id == project["id"]).order_by(Review.id)).all()
    assert [r.content for r in reviews] == ["Great app", "Too slow", "Nice"]
    first = reviews[0]
    assert (first.rating, first.author, first.source, first.import_id, first.created_by) == (
        5, "Maria", ReviewSource.csv, body["id"], owner.id,
    )
    assert first.reviewed_at is not None and first.reviewed_at.year == 2026
    assert first.content_hash == content_hash("Great app")
    assert reviews[2].rating == 4 and reviews[2].author is None and reviews[2].reviewed_at is None


def test_import_record_stores_file_hash(upload, db):
    raw = GOOD.encode()
    import_id = upload(raw).json()["id"]
    assert db.get(Import, import_id).file_sha256 == hashlib.sha256(raw).hexdigest()


def test_external_id_is_kept(upload, db):
    upload("content,id\nGreat,r-77\n")
    assert db.scalars(select(Review)).one().external_id == "r-77"


def test_semicolon_file_with_bom_and_diacritics(upload, db):
    r = upload("﻿Review;Rating\nFoarte bună;5\n")
    assert r.status_code == 201 and r.json()["imported_rows"] == 1
    assert db.scalars(select(Review)).one().content == "Foarte bună"


def test_file_name_check_ignores_case(upload):
    assert upload(name="REVIEWS.CSV").status_code == 201


# Rows with problems ----------------------------------------------------------------------------

BAD_ROWS = "content,rating,author,date\nGreat app,5,Maria,2026-11-01\n,3,Ion,2026-11-02\nToo slow,9,Ana,\nNice,4,,\n"


def test_invalid_rows_are_reported_and_valid_rows_still_imported(upload, db):
    body = upload(BAD_ROWS).json()
    assert (body["total_rows"], body["imported_rows"], body["invalid_rows"], body["duplicate_rows"]) == (4, 2, 2, 0)
    assert [(e["row_number"], e["field"]) for e in body["errors"]] == [(3, "content"), (4, "rating")]
    assert all(e["message"] for e in body["errors"])
    assert sorted(r.content for r in db.scalars(select(Review))) == ["Great app", "Nice"]


def test_row_with_several_problems_gets_one_error_each(upload):
    body = upload("content,rating,date\n,9,nope\n").json()
    assert body["invalid_rows"] == 1  # one row...
    assert [e["field"] for e in body["errors"]] == ["content", "rating", "date"]  # ...three problems


def test_all_rows_invalid_still_completes_with_nothing_imported(upload, db):
    r = upload("content,rating\nA,0\nB,7\n")
    assert r.status_code == 201 and r.json()["imported_rows"] == 0 and r.json()["invalid_rows"] == 2
    assert db.scalars(select(Review)).all() == []


def test_blank_rows_are_not_reviews(upload):
    assert upload("content\n \n,\n").status_code == 422  # nothing to import


def test_stored_errors_are_capped(upload):
    rows = "\n".join(["content,rating"] + ["x,9"] * (MAX_STORED_ERRORS + 100))
    body = upload(rows).json()
    assert body["invalid_rows"] == MAX_STORED_ERRORS + 100
    assert len(body["errors"]) == MAX_STORED_ERRORS


# Duplicates ------------------------------------------------------------------------------------

def test_duplicates_inside_the_file_are_skipped(upload):
    body = upload("content\nGreat app\n  great   APP \nOther\n").json()
    assert (body["total_rows"], body["imported_rows"], body["duplicate_rows"]) == (3, 2, 1)


def test_review_that_already_exists_is_skipped(client, upload, owner, auth, url, project, db):
    client.post(f"/projects/{project['id']}/reviews", json={"content": "Great app"}, headers=auth(owner))
    body = upload("content\nGreat app\nNew one\n").json()
    assert (body["imported_rows"], body["duplicate_rows"]) == (1, 1)
    assert len(db.scalars(select(Review)).all()) == 2


def test_importing_the_same_file_twice_adds_nothing(upload, db):
    assert upload().json()["imported_rows"] == 3
    second = upload().json()
    assert (second["imported_rows"], second["duplicate_rows"]) == (0, 3)
    assert len(db.scalars(select(Review)).all()) == 3


def test_same_reviews_can_be_imported_into_another_project(client, upload, owner, auth):
    upload()
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    r = upload(target=f"/projects/{other['id']}/imports")
    assert r.json()["imported_rows"] == 3


def test_concurrent_duplicate_is_a_conflict_and_nothing_is_saved(upload, db, monkeypatch, client, owner, auth, project):
    client.post(f"/projects/{project['id']}/reviews", json={"content": "Great app"}, headers=auth(owner))
    monkeypatch.setattr(import_service, "existing_hashes", lambda *a, **k: set())  # the check "missed" it
    assert upload("content\nGreat app\nOther\n").status_code == 409
    assert db.scalars(select(Import)).all() == []
    assert len(db.scalars(select(Review)).all()) == 1


# Files that cannot be read ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "content,name",
    [
        (b"", "reviews.csv"),
        ("rating,author\n5,Maria\n", "reviews.csv"),
        ("content,rating\n", "reviews.csv"),
        ("content\nfoarte bună\n".encode("cp1250"), "reviews.csv"),
        (GOOD, "reviews.xlsx"),
        (GOOD, "reviews"),
        (GOOD, ""),
    ],
    ids=["empty", "no-content-column", "header-only", "not-utf8", "wrong-extension", "no-extension", "no-name"],
)
def test_unreadable_file_is_rejected_and_leaves_no_trace(upload, db, content, name):
    r = upload(content, name=name)
    assert r.status_code == 422
    assert r.json()["detail"]
    assert db.scalars(select(Import)).all() == [] and db.scalars(select(Review)).all() == []


def test_file_too_large(upload):
    r = upload(b"a" * (MAX_FILE_BYTES + 1))
    assert r.status_code == 413


def test_file_at_the_size_limit_is_accepted(upload):
    rows = [f"{i:04d} " + "x" * 8000 for i in range(300)]  # long, all different
    raw = ("content\n" + "\n".join(rows) + "\n").encode()[:MAX_FILE_BYTES]
    assert len(raw) == MAX_FILE_BYTES
    r = upload(raw)
    assert r.status_code == 201
    assert r.json()["invalid_rows"] == 0 and r.json()["imported_rows"] == r.json()["total_rows"] > 200


def test_file_field_is_required(client, owner, auth, url):
    assert client.post(url, headers=auth(owner)).status_code == 422


# History -----------------------------------------------------------------------------------------

def test_list_imports_newest_first(client, upload, owner, auth, url):
    first = upload(name="a.csv").json()["id"]
    second = upload("content\nOther\n", name="b.csv").json()["id"]
    body = client.get(url, headers=auth(owner)).json()
    assert [i["id"] for i in body] == [second, first]
    assert [i["file_name"] for i in body] == ["b.csv", "a.csv"]
    assert "errors" not in body[0]


def test_list_is_empty_at_first(client, owner, auth, url):
    assert client.get(url, headers=auth(owner)).json() == []


def test_list_only_this_projects_imports(client, upload, owner, auth, url):
    upload()
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    assert client.get(f"/projects/{other['id']}/imports", headers=auth(owner)).json() == []


def test_get_import_with_errors(client, upload, owner, auth, url):
    import_id = upload(BAD_ROWS).json()["id"]
    body = client.get(f"{url}/{import_id}", headers=auth(owner)).json()
    assert body["invalid_rows"] == 2 and [e["row_number"] for e in body["errors"]] == [3, 4]


def test_errors_are_loaded_before_the_session_closes(upload, db):
    """In production the session is closed before the response is built, so no lazy loading may be left."""
    run = import_service._with_errors(db, upload(BAD_ROWS).json()["id"])
    assert "errors" not in inspect(run).unloaded and len(run.errors) == 2


def test_unknown_import_404(client, owner, auth, url):
    assert client.get(f"{url}/999", headers=auth(owner)).status_code == 404


def test_import_of_another_project_is_404(client, upload, owner, auth):
    import_id = upload().json()["id"]
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    assert client.get(f"/projects/{other['id']}/imports/{import_id}", headers=auth(owner)).status_code == 404


# Permissions -------------------------------------------------------------------------------------

def test_analyst_can_import(upload, member):
    analyst = member("analyst@x.io", "analyst")
    r = upload(user=analyst)
    assert r.status_code == 201 and r.json()["uploaded_by"] == str(analyst.id)


@pytest.mark.parametrize("role", ["product_manager", "viewer"])
def test_other_roles_can_read_history_but_not_import(client, upload, member, auth, url, role):
    import_id = upload().json()["id"]
    user = member(f"{role}@x.io", role)
    assert [i["id"] for i in client.get(url, headers=auth(user)).json()] == [import_id]
    assert client.get(f"{url}/{import_id}", headers=auth(user)).status_code == 200
    assert upload(user=user).status_code == 403


def test_non_member_gets_404(client, upload, make_user, auth, url):
    upload()
    stranger = make_user("stranger@x.io")
    assert client.get(url, headers=auth(stranger)).status_code == 404
    assert upload(user=stranger).status_code == 404


def test_requires_authentication(client, url):
    assert client.get(url).status_code == 401
    assert client.post(url, files={"file": ("a.csv", b"content\nx\n", "text/csv")}).status_code == 401


def test_archived_project_is_read_only(client, upload, owner, auth, url, project):
    upload()
    assert client.delete(f"/projects/{project['id']}", headers=auth(owner)).status_code == 204
    assert len(client.get(url, headers=auth(owner)).json()) == 1
    assert upload("content\nNew\n").status_code == 409


# Audit -------------------------------------------------------------------------------------------

def test_import_is_audited(upload, owner, db, project):
    import_id = upload(BAD_ROWS).json()["id"]
    row = db.scalars(select(AuditLog).where(AuditLog.project_id == project["id"], AuditLog.target_type == "import")).one()
    assert (row.action, row.target_id, row.actor_id) == ("import.completed", import_id, owner.id)
    assert row.details == {
        "file_name": "reviews.csv", "total_rows": 4, "imported_rows": 2, "duplicate_rows": 0, "invalid_rows": 2,
    }


def test_rejected_files_are_not_audited(upload, db, project):
    upload(b"")
    upload(GOOD, name="x.txt")
    assert db.scalars(select(AuditLog).where(AuditLog.target_type == "import")).all() == []
