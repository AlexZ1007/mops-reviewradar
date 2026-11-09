"""Story #4: owners configure custom feedback categories per project."""
import pytest
from sqlalchemy import select

from app.models import AuditLog, Category


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
    return f"/projects/{project['id']}/categories"


@pytest.fixture
def member(client, db, make_user, auth, owner, project):
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
def create(client, owner, auth, url):
    def _create(name, color=None, **kw):
        body = {"name": name} if color is None else {"name": name, "color": color}
        return client.post(url, json=body, headers=auth(kw.get("user", owner)))

    return _create


def names(response):
    assert response.status_code == 200
    return [c["name"] for c in response.json()]


# Create ---------------------------------------------------------------------------

def test_create_category(client, create, project):
    r = create("Billing", "#B0122B")
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Billing"
    assert body["color"] == "#b0122b"  # normalised to lower case
    assert body["project_id"] == project["id"]
    assert isinstance(body["id"], int)


def test_color_is_optional(create):
    assert create("Login").json()["color"] is None


def test_name_is_trimmed(create):
    assert create("  Shipping  ").json()["name"] == "Shipping"


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_blank_name_rejected(create, name):
    assert create(name).status_code == 422


def test_name_length_limit(create):
    assert create("x" * 80).status_code == 201
    assert create("y" * 81).status_code == 422


def test_name_required(client, owner, auth, url):
    assert client.post(url, json={}, headers=auth(owner)).status_code == 422
    assert client.post(url, json={"name": None}, headers=auth(owner)).status_code == 422


@pytest.mark.parametrize("color", ["red", "#fff", "#12345", "#1234567", "123456", "#ggg000", "", "#12 456"])
def test_invalid_color_rejected(create, color):
    assert create("Bad", color).status_code == 422


def test_duplicate_name_409_case_insensitive(create):
    assert create("Billing").status_code == 201
    assert create("Billing").status_code == 409
    assert create("billing").status_code == 409
    assert create("  BILLING ").status_code == 409


def test_same_name_allowed_in_another_project(client, create, owner, auth):
    assert create("Billing").status_code == 201
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    r = client.post(f"/projects/{other['id']}/categories", json={"name": "Billing"}, headers=auth(owner))
    assert r.status_code == 201


# Read / filter ---------------------------------------------------------------------

def test_list_empty(client, owner, auth, url):
    assert client.get(url, headers=auth(owner)).json() == []


def test_list_ordered_by_name_ignoring_case(client, create, owner, auth, url):
    for n in ["pricing", "Billing", "Zoom", "alerts"]:
        create(n)
    assert names(client.get(url, headers=auth(owner))) == ["alerts", "Billing", "pricing", "Zoom"]


@pytest.fixture
def seeded(create):
    for n in ["Billing", "Billing errors", "Login", "Slow performance", "100% crashes", "a_b"]:
        assert create(n).status_code == 201


def test_filter_by_name_substring(client, seeded, owner, auth, url):
    assert names(client.get(url, params={"q": "bill"}, headers=auth(owner))) == ["Billing", "Billing errors"]
    assert names(client.get(url, params={"q": "PERFORM"}, headers=auth(owner))) == ["Slow performance"]


def test_filter_no_match(client, seeded, owner, auth, url):
    assert client.get(url, params={"q": "refund"}, headers=auth(owner)).json() == []


@pytest.mark.parametrize("q", ["", "   "])
def test_blank_filter_returns_everything(client, seeded, owner, auth, url, q):
    assert len(client.get(url, params={"q": q}, headers=auth(owner)).json()) == 6


def test_filter_treats_wildcards_literally(client, seeded, owner, auth, url):
    assert names(client.get(url, params={"q": "%"}, headers=auth(owner))) == ["100% crashes"]
    assert names(client.get(url, params={"q": "a_b"}, headers=auth(owner))) == ["a_b"]
    assert names(client.get(url, params={"q": "_"}, headers=auth(owner))) == ["a_b"]


def test_filter_query_too_long(client, owner, auth, url):
    assert client.get(url, params={"q": "x" * 81}, headers=auth(owner)).status_code == 422


def test_list_only_this_projects_categories(client, create, owner, auth):
    create("Mine")
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    client.post(f"/projects/{other['id']}/categories", json={"name": "Theirs"}, headers=auth(owner))
    assert names(client.get(f"/projects/{other['id']}/categories", headers=auth(owner))) == ["Theirs"]


def test_get_one(client, create, owner, auth, url):
    cid = create("Billing", "#112233").json()["id"]
    r = client.get(f"{url}/{cid}", headers=auth(owner))
    assert r.status_code == 200 and r.json()["name"] == "Billing"


# Update ----------------------------------------------------------------------------

def test_rename_and_recolor(client, create, owner, auth, url):
    cid = create("Billing", "#112233").json()["id"]
    r = client.patch(f"{url}/{cid}", json={"name": " Payments ", "color": "#AABBCC"}, headers=auth(owner))
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["color"]) == ("Payments", "#aabbcc")


def test_patch_only_touches_sent_fields(client, create, owner, auth, url):
    cid = create("Billing", "#112233").json()["id"]
    r = client.patch(f"{url}/{cid}", json={"name": "Payments"}, headers=auth(owner))
    assert (r.json()["name"], r.json()["color"]) == ("Payments", "#112233")
    r = client.patch(f"{url}/{cid}", json={"color": "#445566"}, headers=auth(owner))
    assert (r.json()["name"], r.json()["color"]) == ("Payments", "#445566")


def test_patch_null_color_clears_it(client, create, owner, auth, url):
    cid = create("Billing", "#112233").json()["id"]
    r = client.patch(f"{url}/{cid}", json={"color": None}, headers=auth(owner))
    assert r.status_code == 200 and r.json()["color"] is None


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "  "}, {"name": None}, {"name": "x" * 81}, {"color": "blue"}])
def test_patch_validation(client, create, owner, auth, url, body):
    cid = create("Billing").json()["id"]
    assert client.patch(f"{url}/{cid}", json=body, headers=auth(owner)).status_code == 422


def test_rename_to_existing_name_409(client, create, owner, auth, url):
    create("Billing")
    cid = create("Login").json()["id"]
    assert client.patch(f"{url}/{cid}", json={"name": "BILLING"}, headers=auth(owner)).status_code == 409


def test_rename_to_own_name_with_other_case_ok(client, create, owner, auth, url):
    cid = create("billing").json()["id"]
    r = client.patch(f"{url}/{cid}", json={"name": "Billing"}, headers=auth(owner))
    assert r.status_code == 200 and r.json()["name"] == "Billing"


def test_update_unknown_category_404(client, owner, auth, url):
    assert client.patch(f"{url}/999", json={"name": "x"}, headers=auth(owner)).status_code == 404


# Delete ----------------------------------------------------------------------------

def test_delete_category(client, create, owner, auth, url, db):
    cid = create("Billing").json()["id"]
    assert client.delete(f"{url}/{cid}", headers=auth(owner)).status_code == 204
    assert client.get(f"{url}/{cid}", headers=auth(owner)).status_code == 404
    assert db.get(Category, cid) is None
    assert client.delete(f"{url}/{cid}", headers=auth(owner)).status_code == 404


def test_name_reusable_after_delete(client, create, owner, auth, url):
    cid = create("Billing").json()["id"]
    client.delete(f"{url}/{cid}", headers=auth(owner))
    assert create("Billing").status_code == 201


# Association with projects -------------------------------------------------------------

def test_category_of_another_project_is_404(client, create, owner, auth):
    cid = create("Billing").json()["id"]
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    base = f"/projects/{other['id']}/categories/{cid}"
    assert client.get(base, headers=auth(owner)).status_code == 404
    assert client.patch(base, json={"name": "x"}, headers=auth(owner)).status_code == 404
    assert client.delete(base, headers=auth(owner)).status_code == 404


# Permissions -------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["analyst", "product_manager", "viewer"])
def test_non_owner_members_can_read_but_not_write(client, create, member, auth, url, role):
    cid = create("Billing").json()["id"]
    user = member(f"{role}@x.io", role)
    h = auth(user)
    assert names(client.get(url, headers=h)) == ["Billing"]
    assert client.get(f"{url}/{cid}", headers=h).status_code == 200
    assert client.post(url, json={"name": "New"}, headers=h).status_code == 403
    assert client.patch(f"{url}/{cid}", json={"name": "New"}, headers=h).status_code == 403
    assert client.delete(f"{url}/{cid}", headers=h).status_code == 403
    assert names(client.get(url, headers=auth(user))) == ["Billing"]


def test_promoted_member_can_manage(client, member, owner, auth, url, project):
    user = member("pm@x.io", "viewer")
    assert client.post(url, json={"name": "A"}, headers=auth(user)).status_code == 403
    r = client.patch(f"/projects/{project['id']}/members/{user.id}", json={"role": "owner"}, headers=auth(owner))
    assert r.status_code == 200
    assert client.post(url, json={"name": "A"}, headers=auth(user)).status_code == 201


def test_non_member_gets_404(client, create, make_user, auth, url):
    create("Billing")
    stranger = make_user("stranger@x.io")
    h = auth(stranger)
    assert client.get(url, headers=h).status_code == 404
    assert client.post(url, json={"name": "x"}, headers=h).status_code == 404


def test_requires_authentication(client, url):
    assert client.get(url).status_code == 401
    assert client.post(url, json={"name": "x"}).status_code == 401


def test_archived_project_is_read_only(client, create, owner, auth, url, project):
    cid = create("Billing").json()["id"]
    assert client.delete(f"/projects/{project['id']}", headers=auth(owner)).status_code == 204
    h = auth(owner)
    assert names(client.get(url, headers=h)) == ["Billing"]
    assert client.post(url, json={"name": "New"}, headers=h).status_code == 409
    assert client.patch(f"{url}/{cid}", json={"name": "New"}, headers=h).status_code == 409
    assert client.delete(f"{url}/{cid}", headers=h).status_code == 409


# Audit ---------------------------------------------------------------------------------

def test_changes_are_audited(client, create, owner, auth, url, db, project):
    cid = create("Billing", "#112233").json()["id"]
    client.patch(f"{url}/{cid}", json={"name": "Payments"}, headers=auth(owner))
    client.delete(f"{url}/{cid}", headers=auth(owner))
    rows = db.scalars(
        select(AuditLog).where(AuditLog.project_id == project["id"], AuditLog.target_type == "category").order_by(AuditLog.id)
    ).all()
    assert [r.action for r in rows] == ["category.created", "category.updated", "category.deleted"]
    assert all(r.target_id == cid and r.actor_id == owner.id for r in rows)
    assert rows[1].details == {"name": "Payments"}


def test_failed_requests_are_not_audited(client, create, owner, auth, url, db, project):
    create("Billing")
    create("Billing")  # 409
    create("")  # 422
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.project_id == project["id"]))]
    assert actions.count("category.created") == 1
