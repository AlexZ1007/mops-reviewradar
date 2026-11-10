"""Story #8: telling the user which rows were duplicates, and when the very same file comes again."""
import pytest

from app.imports.duplicates import existing_review_ids
from app.imports.service import MAX_REPORTED_DUPLICATES
from app.models import Review, ReviewSource
from app.reviews.hashing import content_hash

FILE = "content,rating\nGreat app,5\nToo slow,2\nNice,4\n"


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
def upload(client, owner, auth, url):
    def _upload(content=FILE, *, target=None, name="reviews.csv"):
        return client.post(target or url, files={"file": (name, content.encode(), "text/csv")}, headers=auth(owner))

    return _upload


# Which rows were duplicates ------------------------------------------------------------------------------

def test_first_import_has_no_duplicates(upload):
    body = upload().json()
    assert body["duplicates"] == [] and body["repeat_of"] is None


def test_duplicate_of_a_review_that_was_already_saved(client, upload, owner, auth, project):
    manual = client.post(f"/projects/{project['id']}/reviews", json={"content": "Great app"}, headers=auth(owner)).json()
    body = upload("content\nGreat app\nNew one\n").json()
    assert body["duplicate_rows"] == 1
    assert body["duplicates"] == [
        {"row_number": 2, "content": "Great app", "of_review_id": manual["id"], "of_row": None}
    ]


def test_duplicate_of_an_earlier_row_of_the_same_file(upload):
    body = upload("content\nGreat app\nOther\n  great   APP \n").json()
    assert body["duplicates"] == [{"row_number": 4, "content": "great   APP", "of_review_id": None, "of_row": 2}]


def test_second_upload_lists_every_row_as_a_duplicate_of_a_saved_review(client, upload, owner, auth, project):
    upload()
    saved = {
        r["content"]: r["id"] for r in client.get(f"/projects/{project['id']}/reviews", headers=auth(owner)).json()
    }
    body = upload().json()
    assert body["imported_rows"] == 0
    assert [(d["row_number"], d["content"], d["of_review_id"]) for d in body["duplicates"]] == [
        (2, "Great app", saved["Great app"]),
        (3, "Too slow", saved["Too slow"]),
        (4, "Nice", saved["Nice"]),
    ]


def test_long_text_is_shortened_in_the_report(upload):
    body = upload("content\n" + "a" * 300 + "\n" + "a" * 300 + "\n").json()
    text = body["duplicates"][0]["content"]
    assert len(text) <= 101 and text.endswith("…")


def test_the_report_is_capped(upload):
    body = upload("content\n" + "same\n" * (MAX_REPORTED_DUPLICATES + 100)).json()
    assert body["duplicate_rows"] == MAX_REPORTED_DUPLICATES + 99  # the true count is kept
    assert len(body["duplicates"]) == MAX_REPORTED_DUPLICATES


def test_duplicates_are_not_kept_in_the_history(client, upload, owner, auth, url):
    import_id = upload("content\nSame\nSame\n").json()["id"]
    assert client.get(f"{url}/{import_id}", headers=auth(owner)).json()["duplicates"] == []


# The same file again ---------------------------------------------------------------------------------------

def test_same_file_again_points_to_the_first_import(upload):
    first = upload().json()
    second = upload().json()
    third = upload().json()
    assert first["repeat_of"] is None
    assert second["repeat_of"] == first["id"]
    assert third["repeat_of"] == first["id"]  # always the first time it was seen


def test_a_different_file_is_not_a_repeat(upload):
    upload()
    assert upload("content\nSomething else\n").json()["repeat_of"] is None


def test_same_file_in_another_project_is_not_a_repeat(client, upload, owner, auth):
    upload()
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    assert upload(target=f"/projects/{other['id']}/imports").json()["repeat_of"] is None


def test_repeat_is_also_shown_by_get_and_list(client, upload, owner, auth, url):
    first = upload().json()["id"]
    second = upload().json()["id"]
    assert client.get(f"{url}/{second}", headers=auth(owner)).json()["repeat_of"] == first
    assert client.get(f"{url}/{first}", headers=auth(owner)).json()["repeat_of"] is None
    listed = {i["id"]: i["repeat_of"] for i in client.get(url, headers=auth(owner)).json()}
    assert listed == {first: None, second: first}


def test_a_file_with_the_same_name_but_other_content_is_not_a_repeat(upload):
    upload("content\nOne\n", name="reviews.csv")
    assert upload("content\nTwo\n", name="reviews.csv").json()["repeat_of"] is None


# The lookup ---------------------------------------------------------------------------------------------------

def test_existing_review_ids_maps_hashes_to_ids_in_chunks(client, owner, auth, project, db):
    reviews = [
        Review(project_id=project["id"], source=ReviewSource.csv, content=f"r{i}", content_hash=content_hash(f"r{i}"))
        for i in range(1200)  # more than one chunk, and more than SQLite's parameter limit if sent at once
    ]
    db.add_all(reviews)
    db.commit()
    wanted = [content_hash(f"r{i}") for i in range(1200)] + ["0" * 64]
    found = existing_review_ids(db, project["id"], wanted)
    assert found == {r.content_hash: r.id for r in reviews}


def test_existing_review_ids_ignores_other_projects(client, owner, auth, project, db):
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    db.add(Review(project_id=other["id"], source=ReviewSource.csv, content="x", content_hash=content_hash("x")))
    db.commit()
    assert existing_review_ids(db, project["id"], [content_hash("x")]) == {}
