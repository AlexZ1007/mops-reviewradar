import pytest
from sqlalchemy import select

from app.models import AuditLog, ProjectMember, ProjectRole
from app.projects.permissions import PERMISSIONS, has_permission


@pytest.fixture
def owner(make_user):
    return make_user("owner@x.io")


@pytest.fixture
def project(client, owner, auth):
    r = client.post("/projects", json={"name": "App", "description": "d"}, headers=auth(owner))
    assert r.status_code == 201
    return r.json()


def add(client, project, actor, auth, email, role):
    return client.post(f"/projects/{project['id']}/members", json={"email": email, "role": role}, headers=auth(actor))


def audit_actions(db, project_id):
    return [a.action for a in db.scalars(select(AuditLog).where(AuditLog.project_id == project_id).order_by(AuditLog.id))]


# Permission map ---------------------------------------------------------------

def test_permission_matrix():
    assert has_permission(ProjectRole.owner, "members.manage")
    assert not has_permission(ProjectRole.analyst, "members.manage")
    assert has_permission(ProjectRole.viewer, "project.read")
    assert not has_permission(ProjectRole.viewer, "results.export")
    assert has_permission(ProjectRole.product_manager, "issues.write")
    assert not has_permission(None, "project.read")
    assert all(ProjectRole.owner in roles for roles in PERMISSIONS.values())
    with pytest.raises(KeyError):
        has_permission(ProjectRole.owner, "nope")


# Projects -------------------------------------------------------------------

def test_creator_becomes_owner(db, project, owner):
    assert project["my_role"] == "owner"
    member = db.get(ProjectMember, (project["id"], owner.id))
    assert member.role == ProjectRole.owner
    assert audit_actions(db, project["id"]) == ["project.created"]


@pytest.mark.parametrize("name", ["", "   "])
def test_name_required(client, owner, auth, name):
    assert client.post("/projects", json={"name": name}, headers=auth(owner)).status_code == 422


def test_duplicate_active_name_409(client, project, owner, auth):
    assert client.post("/projects", json={"name": "app"}, headers=auth(owner)).status_code == 409


def test_same_name_allowed_after_archive(client, project, owner, auth):
    assert client.delete(f"/projects/{project['id']}", headers=auth(owner)).status_code == 204
    assert client.post("/projects", json={"name": "App"}, headers=auth(owner)).status_code == 201


def test_list_only_own_projects(client, project, owner, make_user, auth):
    other = make_user("other@x.io")
    client.post("/projects", json={"name": "Other"}, headers=auth(other))
    assert [p["name"] for p in client.get("/projects", headers=auth(owner)).json()] == ["App"]
    assert [p["name"] for p in client.get("/projects", headers=auth(other)).json()] == ["Other"]


def test_update_project(client, db, project, owner, auth):
    r = client.patch(f"/projects/{project['id']}", json={"name": "New"}, headers=auth(owner))
    assert r.status_code == 200 and r.json()["name"] == "New"
    assert "project.updated" in audit_actions(db, project["id"])


def test_archived_project_hidden_and_read_only(client, project, owner, auth):
    pid = project["id"]
    client.delete(f"/projects/{pid}", headers=auth(owner))
    assert client.get("/projects", headers=auth(owner)).json() == []
    assert client.get(f"/projects/{pid}", headers=auth(owner)).status_code == 200
    assert client.patch(f"/projects/{pid}", json={"name": "X"}, headers=auth(owner)).status_code == 409
    assert add(client, project, owner, auth, "owner@x.io", "viewer").status_code == 409


def test_unauthenticated_project_request_401(client, project):
    assert client.get(f"/projects/{project['id']}").status_code == 401


# Access ---------------------------------------------------------------------

def test_non_member_gets_404(client, project, make_user, auth):
    stranger = make_user("s@x.io")
    assert client.get(f"/projects/{project['id']}", headers=auth(stranger)).status_code == 404
    assert client.get("/projects/9999", headers=auth(stranger)).status_code == 404


def test_viewer_cannot_write(client, project, owner, make_user, auth):
    viewer = make_user("v@x.io")
    add(client, project, owner, auth, "v@x.io", "viewer")
    pid = project["id"]
    assert client.get(f"/projects/{pid}", headers=auth(viewer)).json()["my_role"] == "viewer"
    assert client.patch(f"/projects/{pid}", json={"name": "X"}, headers=auth(viewer)).status_code == 403
    assert add(client, project, viewer, auth, "owner@x.io", "viewer").status_code == 403


def test_admin_passes_project_checks(client, project, make_user, auth):
    admin = make_user("a@x.io", is_admin=True)
    pid = project["id"]
    r = client.get(f"/projects/{pid}", headers=auth(admin))
    assert r.status_code == 200 and r.json()["my_role"] is None
    assert client.patch(f"/projects/{pid}", json={"description": "fixed"}, headers=auth(admin)).status_code == 200


# Members --------------------------------------------------------------------

def test_add_member_by_email(client, db, project, owner, make_user, auth):
    make_user("Ana@X.io", full_name="Ana")
    r = add(client, project, owner, auth, "ana@x.io", "analyst")
    assert r.status_code == 201
    assert r.json()["role"] == "analyst" and r.json()["full_name"] == "Ana"
    members = client.get(f"/projects/{project['id']}/members", headers=auth(owner)).json()
    assert {m["email"] for m in members} == {"owner@x.io", "Ana@X.io"}
    assert audit_actions(db, project["id"])[-1] == "member.added"


def test_add_unknown_or_inactive_email_404(client, project, owner, make_user, auth):
    make_user("off@x.io", is_active=False)
    assert add(client, project, owner, auth, "ghost@x.io", "viewer").status_code == 404
    assert add(client, project, owner, auth, "off@x.io", "viewer").status_code == 404


def test_add_duplicate_409(client, project, owner, make_user, auth):
    make_user("v@x.io")
    add(client, project, owner, auth, "v@x.io", "viewer")
    assert add(client, project, owner, auth, "v@x.io", "analyst").status_code == 409


def test_change_role_applies_immediately(client, db, project, owner, make_user, auth):
    user = make_user("v@x.io")
    add(client, project, owner, auth, "v@x.io", "viewer")
    pid = project["id"]
    assert client.patch(f"/projects/{pid}", json={"description": "x"}, headers=auth(user)).status_code == 403
    r = client.patch(f"/projects/{pid}/members/{user.id}", json={"role": "owner"}, headers=auth(owner))
    assert r.status_code == 200 and r.json()["role"] == "owner"
    assert client.patch(f"/projects/{pid}", json={"description": "x"}, headers=auth(user)).status_code == 200
    log = db.scalars(select(AuditLog).where(AuditLog.action == "member.role_changed")).one()
    assert log.details == {"user_id": str(user.id), "old_role": "viewer", "new_role": "owner"}


def test_remove_member(client, db, project, owner, make_user, auth):
    user = make_user("v@x.io")
    add(client, project, owner, auth, "v@x.io", "viewer")
    pid = project["id"]
    assert client.delete(f"/projects/{pid}/members/{user.id}", headers=auth(owner)).status_code == 204
    assert client.get(f"/projects/{pid}", headers=auth(user)).status_code == 404
    assert audit_actions(db, pid)[-1] == "member.removed"


def test_change_or_remove_unknown_member_404(client, project, owner, make_user, auth):
    other = make_user("o@x.io")
    pid = project["id"]
    assert client.patch(f"/projects/{pid}/members/{other.id}", json={"role": "viewer"}, headers=auth(owner)).status_code == 404
    assert client.delete(f"/projects/{pid}/members/{other.id}", headers=auth(owner)).status_code == 404


def test_non_owner_cannot_remove_others_but_can_leave(client, project, owner, make_user, auth):
    a = make_user("a@x.io")
    add(client, project, owner, auth, "a@x.io", "analyst")
    pid = project["id"]
    assert client.delete(f"/projects/{pid}/members/{owner.id}", headers=auth(a)).status_code == 403
    assert client.delete(f"/projects/{pid}/members/{a.id}", headers=auth(a)).status_code == 204


# Last owner -------------------------------------------------------------------

def test_last_owner_cannot_be_demoted_removed_or_leave(client, db, project, owner, auth):
    pid = project["id"]
    assert client.patch(f"/projects/{pid}/members/{owner.id}", json={"role": "viewer"}, headers=auth(owner)).status_code == 409
    assert client.delete(f"/projects/{pid}/members/{owner.id}", headers=auth(owner)).status_code == 409
    assert db.get(ProjectMember, (pid, owner.id)).role == ProjectRole.owner


def test_owner_can_leave_when_another_owner_exists(client, project, owner, make_user, auth):
    other = make_user("o2@x.io")
    add(client, project, owner, auth, "o2@x.io", "owner")
    pid = project["id"]
    assert client.delete(f"/projects/{pid}/members/{owner.id}", headers=auth(owner)).status_code == 204
    assert client.patch(f"/projects/{pid}/members/{other.id}", json={"role": "viewer"}, headers=auth(other)).status_code == 409


def test_each_membership_change_writes_one_audit_row(client, db, project, owner, make_user, auth):
    user = make_user("v@x.io")
    pid = project["id"]
    add(client, project, owner, auth, "v@x.io", "viewer")
    client.patch(f"/projects/{pid}/members/{user.id}", json={"role": "analyst"}, headers=auth(owner))
    client.delete(f"/projects/{pid}/members/{user.id}", headers=auth(owner))
    assert audit_actions(db, pid) == ["project.created", "member.added", "member.role_changed", "member.removed"]


def test_add_member_with_local_domain_and_bad_email(client, project, owner, make_user, auth):
    make_user("admin@reviewradar.local")
    assert add(client, project, owner, auth, "admin@reviewradar.local", "viewer").status_code == 201
    assert add(client, project, owner, auth, "not-an-email", "viewer").status_code == 422
