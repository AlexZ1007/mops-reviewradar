from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import AuditLog, InvitationStatus, Notification, ProjectInvitation, ProjectMember, ProjectRole


@pytest.fixture
def owner(make_user):
    return make_user("owner@x.io", full_name="Olga Owner")


@pytest.fixture
def project(client, owner, auth):
    r = client.post("/projects", json={"name": "App"}, headers=auth(owner))
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def invite(client, project, owner, auth):
    def _invite(email, role="analyst", actor=None):
        return client.post(
            f"/projects/{project['id']}/invitations", json={"email": email, "role": role}, headers=auth(actor or owner)
        )

    return _invite


def notifications(client, auth, user, **params):
    return client.get("/notifications", params=params, headers=auth(user)).json()


def unread(client, auth, user):
    return client.get("/notifications/unread-count", headers=auth(user)).json()["count"]


def audit_actions(db, project_id):
    return [a.action for a in db.scalars(select(AuditLog).where(AuditLog.project_id == project_id).order_by(AuditLog.id))]


def expire(db, invitation_id):
    db.get(ProjectInvitation, invitation_id).expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()


# Creating -------------------------------------------------------------------------

def test_invite_existing_user_creates_pending_invitation_and_notification(client, db, project, invite, make_user, auth):
    ana = make_user("Ana@X.io")
    r = invite("ana@x.io")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending" and body["role"] == "analyst" and body["invited_by_name"] == "Olga Owner"
    assert db.get(ProjectMember, (project["id"], ana.id)) is None  # not a member until accepted

    [n] = notifications(client, auth, ana)
    assert n["type"] == "invitation" and n["invitation_status"] == "pending" and n["read_at"] is None
    assert n["payload"] == {"actor_name": "Olga Owner", "project_name": "App", "role": "analyst"}
    assert unread(client, auth, ana) == 1
    assert audit_actions(db, project["id"])[-1] == "invitation.created"


def test_invite_unknown_or_inactive_email_looks_the_same(client, db, invite, make_user):
    make_user("off@x.io", is_active=False)
    a, b = invite("ghost@x.io"), invite("off@x.io")
    assert a.status_code == b.status_code == 201
    assert db.scalars(select(Notification)).all() == []


def test_invite_member_or_duplicate_409(invite, make_user):
    make_user("v@x.io")
    assert invite("owner@x.io").status_code == 409  # already a member
    assert invite("v@x.io").status_code == 201
    assert invite("V@x.io", role="viewer").status_code == 409  # one pending per email, case-insensitive


def test_invite_requires_members_manage(client, project, invite, make_user, auth):
    viewer, stranger = make_user("v@x.io"), make_user("s@x.io")
    inv = invite("v@x.io", role="viewer").json()
    client.post(f"/invitations/{inv['id']}/accept", headers=auth(viewer))
    assert invite("z@x.io", actor=viewer).status_code == 403
    assert invite("z@x.io", actor=stranger).status_code == 404
    assert client.get(f"/projects/{project['id']}/invitations", headers=auth(viewer)).status_code == 403


def test_invite_on_archived_project_409(client, project, owner, invite, auth):
    client.delete(f"/projects/{project['id']}", headers=auth(owner))
    assert invite("v@x.io").status_code == 409


def test_invite_email_validation(invite):
    assert invite("admin@reviewradar.local").status_code == 201
    assert invite("not-an-email").status_code == 422


def test_list_pending_invitations(client, project, owner, invite, auth, db):
    a = invite("a@x.io").json()
    invite("b@x.io")
    expire(db, a["id"])
    listed = client.get(f"/projects/{project['id']}/invitations", headers=auth(owner)).json()
    assert {(i["email"], i["status"]) for i in listed} == {("a@x.io", "expired"), ("b@x.io", "pending")}


def test_reinvite_after_expiry(db, invite):
    first = invite("a@x.io").json()
    expire(db, first["id"])
    assert invite("a@x.io").status_code == 201
    assert db.get(ProjectInvitation, first["id"]).status == InvitationStatus.expired


# Accepting / declining ---------------------------------------------------------------

def test_accept_makes_member_and_notifies_inviter(client, db, project, owner, invite, make_user, auth):
    ana = make_user("ana@x.io", full_name="Ana")
    inv = invite("ana@x.io", role="product_manager").json()
    r = client.post(f"/invitations/{inv['id']}/accept", headers=auth(ana))
    assert r.status_code == 200 and r.json()["id"] == project["id"] and r.json()["my_role"] == "product_manager"

    member = db.get(ProjectMember, (project["id"], ana.id))
    assert member.role == ProjectRole.product_manager and member.added_by == owner.id
    assert db.get(ProjectInvitation, inv["id"]).status == InvitationStatus.accepted
    assert unread(client, auth, ana) == 0
    assert notifications(client, auth, ana)[0]["invitation_status"] == "accepted"

    [n] = notifications(client, auth, owner)
    assert n["type"] == "invitation.accepted" and n["payload"]["actor_name"] == "Ana"
    assert audit_actions(db, project["id"])[-2:] == ["invitation.accepted", "member.added"]


def test_decline(client, db, project, owner, invite, make_user, auth):
    ana = make_user("ana@x.io")
    inv = invite("ana@x.io").json()
    assert client.post(f"/invitations/{inv['id']}/decline", headers=auth(ana)).status_code == 204
    assert db.get(ProjectMember, (project["id"], ana.id)) is None
    assert db.get(ProjectInvitation, inv["id"]).status == InvitationStatus.declined
    assert notifications(client, auth, owner)[0]["type"] == "invitation.declined"
    assert client.post(f"/invitations/{inv['id']}/accept", headers=auth(ana)).status_code == 409
    assert invite("ana@x.io").status_code == 201  # can be invited again


def test_only_the_invited_email_can_answer(client, invite, make_user, auth):
    make_user("ana@x.io")
    other = make_user("eve@x.io")
    inv = invite("ana@x.io").json()
    assert client.post(f"/invitations/{inv['id']}/accept", headers=auth(other)).status_code == 404
    assert client.post(f"/invitations/{inv['id']}/decline", headers=auth(other)).status_code == 404
    assert client.post("/invitations/9999/accept", headers=auth(other)).status_code == 404


def test_expired_invitation_cannot_be_accepted(client, db, invite, make_user, auth):
    ana = make_user("ana@x.io")
    inv = invite("ana@x.io").json()
    expire(db, inv["id"])
    assert notifications(client, auth, ana)[0]["invitation_status"] == "expired"
    r = client.post(f"/invitations/{inv['id']}/accept", headers=auth(ana))
    assert r.status_code == 409 and "expired" in r.json()["detail"]
    assert db.get(ProjectInvitation, inv["id"]).status == InvitationStatus.expired
    assert unread(client, auth, ana) == 0


def test_cannot_accept_for_archived_project(client, project, owner, invite, make_user, auth):
    ana = make_user("ana@x.io")
    inv = invite("ana@x.io").json()
    client.delete(f"/projects/{project['id']}", headers=auth(owner))
    r = client.post(f"/invitations/{inv['id']}/accept", headers=auth(ana))
    assert r.status_code == 409 and "archived" in r.json()["detail"]


def test_accept_twice_409(client, invite, make_user, auth):
    ana = make_user("ana@x.io")
    inv = invite("ana@x.io").json()
    assert client.post(f"/invitations/{inv['id']}/accept", headers=auth(ana)).status_code == 200
    assert client.post(f"/invitations/{inv['id']}/accept", headers=auth(ana)).status_code == 409


def test_user_who_signs_up_later_can_accept(client, db, project, invite, make_user, auth):
    inv = invite("new@x.io").json()
    new = make_user("new@x.io")  # in Postgres the trigger also delivers the notification
    assert client.post(f"/invitations/{inv['id']}/accept", headers=auth(new)).status_code == 200
    assert db.get(ProjectMember, (project["id"], new.id)) is not None


# Revoking -----------------------------------------------------------------------------

def test_revoke(client, db, project, owner, invite, make_user, auth):
    ana = make_user("ana@x.io")
    inv = invite("ana@x.io").json()
    url = f"/projects/{project['id']}/invitations/{inv['id']}"
    assert client.delete(url, headers=auth(owner)).status_code == 204
    assert db.get(ProjectInvitation, inv["id"]).status == InvitationStatus.revoked
    assert unread(client, auth, ana) == 0
    assert notifications(client, auth, ana)[0]["invitation_status"] == "revoked"
    assert client.post(f"/invitations/{inv['id']}/accept", headers=auth(ana)).status_code == 409
    assert client.delete(url, headers=auth(owner)).status_code == 409
    assert client.get(f"/projects/{project['id']}/invitations", headers=auth(owner)).json() == []
    assert audit_actions(db, project["id"])[-1] == "invitation.revoked"


def test_revoke_invitation_of_other_project_404(client, owner, invite, auth):
    inv = invite("ana@x.io").json()
    other = client.post("/projects", json={"name": "Other"}, headers=auth(owner)).json()
    assert client.delete(f"/projects/{other['id']}/invitations/{inv['id']}", headers=auth(owner)).status_code == 404


# Notifications ------------------------------------------------------------------------

def test_mark_read_and_filters(client, invite, make_user, auth, owner):
    ana = make_user("ana@x.io")
    invite("ana@x.io")
    other = client.post("/projects", json={"name": "Second"}, headers=auth(owner)).json()
    client.post(f"/projects/{other['id']}/invitations", json={"email": "ana@x.io", "role": "viewer"}, headers=auth(owner))

    first, second = notifications(client, auth, ana)
    assert first["payload"]["project_name"] == "Second"  # newest first
    assert client.post(f"/notifications/{first['id']}/read", headers=auth(ana)).status_code == 204
    assert [n["id"] for n in notifications(client, auth, ana, unread="true")] == [second["id"]]
    assert client.post("/notifications/read-all", headers=auth(ana)).status_code == 204
    assert unread(client, auth, ana) == 0
    assert len(notifications(client, auth, ana)) == 2


def test_cannot_touch_other_users_notifications(client, invite, make_user, auth):
    ana, eve = make_user("ana@x.io"), make_user("eve@x.io")
    invite("ana@x.io")
    [n] = notifications(client, auth, ana)
    assert notifications(client, auth, eve) == []
    assert client.post(f"/notifications/{n['id']}/read", headers=auth(eve)).status_code == 404
    assert unread(client, auth, ana) == 1


def test_notifications_require_auth(client):
    assert client.get("/notifications").status_code == 401


def test_direct_add_endpoint_removed(client, project, owner, auth):
    r = client.post(f"/projects/{project['id']}/members", json={"email": "a@x.io", "role": "viewer"}, headers=auth(owner))
    assert r.status_code == 405
