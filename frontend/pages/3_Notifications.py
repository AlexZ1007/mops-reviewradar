from html import escape

import streamlit as st

import api_client
import ui
from roles import label

ui.page("Inbox")
ui.top_bar("inbox")
ui.flash()

try:
    everything = api_client.get("/notifications")
except api_client.ApiError as e:
    st.error(e.detail)
    st.stop()

unread_count = sum(1 for n in everything if n["read_at"] is None)

left, right = st.columns([3, 1.3], vertical_alignment="bottom")
with left:
    ui.head("Inbox", f"<span class='rr-num'>{unread_count}</span> unread" if unread_count else "You're all caught up.")
with right, st.container(horizontal=True, horizontal_alignment="right"):
    if st.button("Mark all as read", icon=":material/done_all:", disabled=not unread_count):
        try:
            api_client.post("/notifications/read-all", {})
        except api_client.ApiError as e:
            st.session_state.flash_error = e.detail
        st.rerun()

st.space("small")
view = st.segmented_control(
    "Show", ["Unread", "All"], default="Unread", required=True, label_visibility="collapsed", key="inbox_view",
    format_func=lambda v: f"Unread  {unread_count}" if v == "Unread" else f"All  {len(everything)}",
)
items = [n for n in everything if n["read_at"] is None] if view == "Unread" else everything


def describe(n: dict) -> str:
    p = n["payload"]
    who = f"<b>{escape(p.get('actor_name') or 'Someone')}</b>"
    project = f"<b>{escape(p.get('project_name', 'a project'))}</b>"
    match n["type"]:
        case "invitation":
            return f"{who} invited you to join {project} as {escape(label(p.get('role')))}"
        case "invitation.accepted":
            return f"{who} accepted your invitation to {project}"
        case "invitation.declined":
            return f"{who} declined your invitation to {project}"
    return f"{escape(n['type'])} · {project}"


STATUS_NOTE = {
    "accepted": "You accepted",
    "declined": "You declined",
    "revoked": "No longer available",
    "expired": "Expired",
}


def mark_read(n: dict) -> None:
    if n["read_at"] is None:
        api_client.post(f"/notifications/{n['id']}/read", {})


if not items:
    st.html(
        "<div class='rr-empty'><div class='rr-title'>"
        + ("Nothing new" if view == "Unread" else "No notifications yet")
        + "</div><div class='rr-sub'>Invitations to projects and answers to the invitations you send show up here.</div></div>"
    )

# Invitations waiting for an answer go first.
items = sorted(items, key=lambda n: not (n["type"] == "invitation" and n["invitation_status"] == "pending"))

for n in items:
    unread = n["read_at"] is None
    status = n["invitation_status"]
    actionable = n["type"] == "invitation" and status == "pending"
    note = ui.ago(n["created_at"])
    if n["type"] == "invitation" and status in STATUS_NOTE:
        note += " · " + STATUS_NOTE[status]
    with st.container(key=f"rr-row-{'mark-' if unread or actionable else ''}n-{n['id']}"):
        text, actions = st.columns([3, 1.6], vertical_alignment="center")
        text.html(f"<div class='rr-line'>{describe(n)}</div><div class='rr-sub'>{note}</div>")
        with actions, st.container(horizontal=True, horizontal_alignment="right"):
            if actionable:
                if st.button("Decline", key=f"dec_{n['id']}"):
                    ui.answer_invitation(n["invitation_id"], "decline")
                if st.button("Accept", key=f"acc_{n['id']}", type="primary", icon=":material/check:"):
                    ui.answer_invitation(n["invitation_id"], "accept")
            elif n["project_id"] and (n["type"] == "invitation.accepted" or status == "accepted"):
                if st.button("Open project", key=f"open_{n['id']}", icon=":material/arrow_forward:", icon_position="right"):
                    mark_read(n)
                    ui.open_project(n["project_id"])
            if unread and not actionable:
                if st.button("", key=f"read_{n['id']}", type="tertiary", icon=":material/check:", help="Mark as read"):
                    mark_read(n)
                    st.rerun()
