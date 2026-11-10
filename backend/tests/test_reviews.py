"""Story #9: analysts and owners add reviews by hand."""
import pytest
from sqlalchemy import select

from app.models import AuditLog, Review, ReviewSource
from app.reviews import service as review_service
from app.reviews.hashing import content_hash, normalize_content


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
    return f"/projects/{project['id']}/reviews"


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
def add(client, owner, auth, url):
    def _add(content="Great app", user=None, **extra):
        return client.post(url, json={"content": content, **extra}, headers=auth(user or owner))

    return _add


# Hashing -------------------------------------------------------------------------------

def test_normalize_collapses_whitespace_and_case():
    assert normalize_content("  Great   APP\n\tindeed ") == "great app indeed"


def test_hash_ignores_case_and_whitespace_but_not_words():
    assert content_hash("Great app") == content_hash("  great   APP ")
    assert content_hash("Great app") != content_hash("Great apps")
    assert len(content_hash("x")) == 64


# Create ----------------------------------------------------------------------------------

def test_create_with_content_only(add, project, owner):
    r = add("Love it")
    assert r.status_code == 201
    body = r.json()
    assert body["content"] == "Love it"
    assert body["source"] == "manual"
    assert body["project_id"] == project["id"]
    assert body["created_by"] == str(owner.id)
    assert body["import_id"] is None and body["external_id"] is None
    assert body["rating"] is None and body["author"] is None and body["reviewed_at"] is None
    assert isinstance(body["id"], int)


def test_create_with_all_fields(client, add, owner, auth, project):
    cid = client.post(
        f"/projects/{project['id']}/categories", json={"name": "Billing"}, headers=auth(owner)
    ).json()["id"]
    r = add("Charged twice", rating=2, author="Maria", reviewed_at="2026-11-01T10:30:00Z", category_id=cid)
    assert r.status_code == 201
    body = r.json()
    assert (body["rating"], body["author"], body["category_id"]) == (2, "Maria", cid)
    assert body["reviewed_at"].startswith("2026-11-01T10:30:00")


def test_review_is_stored_with_hash(add, db):
    rid = add("  Great   App ").json()["id"]
    row = db.get(Review, rid)
    assert row.source == ReviewSource.manual
    assert row.content == "Great   App"  # trimmed only: the text itself is kept as typed
    assert row.content_hash == content_hash("great app")


def test_content_is_trimmed(add):
    assert add("  Nice  ").json()["content"] == "Nice"


@pytest.mark.parametrize("content", ["", "   ", "\t\n"])
def test_blank_content_rejected(add, content):
    assert add(content).status_code == 422


def test_content_required(client, owner, auth, url):
    assert client.post(url, json={}, headers=auth(owner)).status_code == 422
    assert client.post(url, json={"content": None}, headers=auth(owner)).status_code == 422


def test_content_length_limit(add):
    assert add("x" * 10_000).status_code == 201
    assert add("y" * 10_001).status_code == 422


@pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
def test_valid_ratings(add, rating):
    r = add(f"Review {rating}", rating=rating)
    assert r.status_code == 201 and r.json()["rating"] == rating


@pytest.mark.parametrize("rating", [0, 6, -1, 4.5, "abc"])
def test_invalid_rating_rejected(add, rating):
    assert add("Some text", rating=rating).status_code == 422


def test_author_is_trimmed_and_blank_becomes_null(add):
    assert add("One", author="  Maria ").json()["author"] == "Maria"
    assert add("Two", author="   ").json()["author"] is None


def test_author_length_limit(add):
    assert add("One", author="a" * 120).status_code == 201
    assert add("Two", author="a" * 121).status_code == 422


def test_invalid_date_rejected(add):
    assert add("One", reviewed_at="yesterday").status_code == 422


def test_date_only_is_accepted(add):
    assert add("One", reviewed_at="2026-11-01").status_code == 201


# Category ----------------------------------------------------------------------------------

def test_unknown_category_rejected(add):
    assert add("One", category_id=999).status_code == 422


def test_category_of_another_project_rejected(client, add, owner, auth):
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    cid = client.post(f"/projects/{other['id']}/categories", json={"name": "Theirs"}, headers=auth(owner)).json()["id"]
    assert add("One", category_id=cid).status_code == 422


# Duplicates --------------------------------------------------------------------------------

def test_duplicate_content_409_ignoring_case_and_spacing(add):
    assert add("Great app").status_code == 201
    assert add("Great app").status_code == 409
    assert add("  GREAT   app ").status_code == 409


def test_concurrent_duplicate_is_a_conflict_and_nothing_is_saved(add, db, monkeypatch, project):
    assert add("Great app").status_code == 201
    monkeypatch.setattr(review_service, "is_duplicate", lambda *a, **k: False)  # the check "missed" it
    assert add("Great app").status_code == 409
    assert len(db.scalars(select(Review)).all()) == 1
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.project_id == project["id"]))]
    assert actions.count("review.created") == 1


def test_same_content_allowed_in_another_project(client, add, owner, auth):
    assert add("Great app").status_code == 201
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    r = client.post(f"/projects/{other['id']}/reviews", json={"content": "Great app"}, headers=auth(owner))
    assert r.status_code == 201


# List ----------------------------------------------------------------------------------------

def test_list_empty(client, owner, auth, url):
    assert client.get(url, headers=auth(owner)).json() == []


def test_list_newest_first(client, add, owner, auth, url):
    for text in ["first", "second", "third"]:
        add(text)
    assert [r["content"] for r in client.get(url, headers=auth(owner)).json()] == ["third", "second", "first"]


def test_list_only_this_projects_reviews(client, add, owner, auth, url):
    add("Mine")
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    client.post(f"/projects/{other['id']}/reviews", json={"content": "Theirs"}, headers=auth(owner))
    assert [r["content"] for r in client.get(url, headers=auth(owner)).json()] == ["Mine"]


def test_list_pagination(client, add, owner, auth, url):
    for i in range(5):
        add(f"Review {i}")
    page = client.get(url, params={"limit": 2, "offset": 1}, headers=auth(owner)).json()
    assert [r["content"] for r in page] == ["Review 3", "Review 2"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_list_pagination_validation(client, owner, auth, url, params):
    assert client.get(url, params=params, headers=auth(owner)).status_code == 422


# Permissions -----------------------------------------------------------------------------------

def test_analyst_can_add(add, member, owner):
    analyst = member("analyst@x.io", "analyst")
    r = add("From analyst", user=analyst)
    assert r.status_code == 201 and r.json()["created_by"] == str(analyst.id)


@pytest.mark.parametrize("role", ["product_manager", "viewer"])
def test_other_roles_can_read_but_not_add(client, add, member, auth, url, role):
    add("Existing")
    user = member(f"{role}@x.io", role)
    assert [r["content"] for r in client.get(url, headers=auth(user)).json()] == ["Existing"]
    assert add("New", user=user).status_code == 403


def test_non_member_gets_404(client, add, make_user, auth, url):
    add("Existing")
    stranger = make_user("stranger@x.io")
    assert client.get(url, headers=auth(stranger)).status_code == 404
    assert add("New", user=stranger).status_code == 404


def test_requires_authentication(client, url):
    assert client.get(url).status_code == 401
    assert client.post(url, json={"content": "x"}).status_code == 401


def test_archived_project_is_read_only(client, add, owner, auth, url, project):
    add("Existing")
    assert client.delete(f"/projects/{project['id']}", headers=auth(owner)).status_code == 204
    assert len(client.get(url, headers=auth(owner)).json()) == 1
    assert add("New").status_code == 409


# Audit -------------------------------------------------------------------------------------------

def test_creation_is_audited(add, owner, db, project):
    rid = add("Audited").json()["id"]
    row = db.scalars(select(AuditLog).where(AuditLog.project_id == project["id"], AuditLog.target_type == "review")).one()
    assert (row.action, row.target_id, row.actor_id) == ("review.created", rid, owner.id)
    assert row.details == {"source": "manual"}


def test_failed_requests_are_not_audited(add, db, project):
    add("Once")
    add("Once")  # 409
    add("")  # 422
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.project_id == project["id"]))]
    assert actions.count("review.created") == 1
