from datetime import UTC, datetime

import streamlit as st

import api_client
import auth
from roles import label

st.set_page_config(page_title="Notifications · ReviewRadar", page_icon="📡")
auth.require_login()
auth.nav_header()

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"))
if "flash_error" in st.session_state:
    st.error(st.session_state.pop("flash_error"))

title, mark_all = st.columns([4, 1.4], vertical_alignment="bottom")
title.title("Notifications")
if mark_all.button("Mark all as read", width="stretch"):
    try:
        api_client.post("/notifications/read-all", {})
        st.rerun()
    except api_client.ApiError as e:
        st.error(e.detail)

view = st.segmented_control("Show", ["Unread", "All"], default="Unread", label_visibility="collapsed") or "Unread"

try:
    items = api_client.get("/notifications" + ("?unread=true" if view == "Unread" else ""))
except api_client.ApiError as e:
    st.error(e.detail)
    st.stop()


def ago(ts: str) -> str:
    when = datetime.fromisoformat(ts)
    when = when if when.tzinfo else when.replace(tzinfo=UTC)
    seconds = (datetime.now(UTC) - when).total_seconds()
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"


def describe(n: dict) -> str:
    p = n["payload"]
    who, project, role = p.get("actor_name") or "Someone", p.get("project_name", "a project"), label(p.get("role"))
    match n["type"]:
        case "invitation":
            return f"**{who}** invited you to join **{project}** as {role}"
        case "invitation.accepted":
            return f"**{who}** accepted your invitation to **{project}**"
        case "invitation.declined":
            return f"**{who}** declined your invitation to **{project}**"
    return f"{n['type']} · {project}"


STATUS_NOTE = {
    "accepted": "You accepted this invitation.",
    "declined": "You declined this invitation.",
    "revoked": "This invitation is no longer available.",
    "expired": "This invitation has expired.",
}


def open_project(project_id: int) -> None:
    st.session_state.project_id = project_id
    st.switch_page("pages/2_Project.py")


def mark_read(n: dict) -> None:
    if n["read_at"] is None:
        api_client.post(f"/notifications/{n['id']}/read", {})


def answer(n: dict, action: str) -> None:
    try:
        result = api_client.post(f"/invitations/{n['invitation_id']}/{action}", {})
    except api_client.ApiError as e:
        st.session_state.flash_error = e.detail
        st.rerun()
    if action == "accept":
        st.session_state.flash = f"You joined {result['name']}"
        open_project(result["id"])
    st.session_state.flash = "Invitation declined"
    st.rerun()


if not items:
    st.info("You're all caught up." if view == "Unread" else "No notifications yet.")

for n in items:
    unread = n["read_at"] is None
    status = n["invitation_status"]
    actionable = n["type"] == "invitation" and status == "pending"
    with st.container(border=True):
        text, buttons = st.columns([3, 1.6], vertical_alignment="center")
        text.markdown(("🔵 " if unread else "") + describe(n))
        caption = ago(n["created_at"])
        if n["type"] == "invitation" and status in STATUS_NOTE:
            caption += " · " + STATUS_NOTE[status]
        text.caption(caption)

        if actionable:
            b1, b2 = buttons.columns(2)
            if b1.button("Accept", key=f"acc_{n['id']}", type="primary", width="stretch"):
                answer(n, "accept")
            if b2.button("Decline", key=f"dec_{n['id']}", width="stretch"):
                answer(n, "decline")
        elif n["project_id"] and (n["type"] == "invitation.accepted" or status == "accepted"):
            if buttons.button("Open project", key=f"open_{n['id']}", width="stretch"):
                mark_read(n)
                open_project(n["project_id"])
        if unread and not actionable:
            if buttons.button("Mark as read", key=f"read_{n['id']}", width="stretch"):
                mark_read(n)
                st.rerun()
