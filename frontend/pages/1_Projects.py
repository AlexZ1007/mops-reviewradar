from html import escape

import streamlit as st

import api_client
import ui
from roles import label

ui.page("Projects")
ui.top_bar("projects")
ui.flash()

if st.session_state.pop("reset_create_project", False):
    st.session_state.new_project_name = ""
    st.session_state.new_project_description = ""

try:
    projects = api_client.get("/projects")
except api_client.ApiError as e:
    st.error(e.detail)
    st.stop()
try:
    notifications = api_client.get("/notifications")
except api_client.ApiError:
    notifications = []  # pending invitations are shown when the API offers them

pending = [n for n in notifications if n["type"] == "invitation" and n["invitation_status"] == "pending"]
owned = [p for p in projects if p["my_role"] == "owner"]

# Head ---------------------------------------------------------------------------
left, right = st.columns([3, 1], vertical_alignment="bottom")
with left:
    if projects:
        meta = f"<span class='rr-num'>{len(projects)}</span> project{'s' if len(projects) != 1 else ''}"
        meta += f" · you own <span class='rr-num'>{len(owned)}</span>" if owned else ""
    else:
        meta = "Projects you create or join appear here."
    ui.head("Projects", meta)
with right, st.container(horizontal=True, horizontal_alignment="right"):
    with st.popover("New project", type="primary", icon=":material/add:"):
        with st.form("create_project", border=False):
            name = st.text_input("Project name", key="new_project_name", max_chars=120, placeholder="e.g. Mobile app reviews")
            description = st.text_area(
                "Description", key="new_project_description", placeholder="What feedback will this project collect? (optional)",
                height=90,
            )
            if st.form_submit_button("Create project", type="primary", width="stretch"):
                if not name.strip():
                    st.warning("Give the project a name.")
                else:
                    try:
                        created = api_client.post(
                            "/projects", {"name": name.strip(), "description": description.strip() or None}
                        )
                    except api_client.ApiError as e:
                        st.error(e.detail)
                    else:
                        st.session_state.reset_create_project = True
                        st.session_state.flash = f"Created {created['name']}"
                        ui.open_project(created["id"])

# Waiting for your answer ----------------------------------------------------------
if pending:
    ui.section("Waiting for your answer")
    for n in pending:
        p = n["payload"]
        who = escape(p.get("actor_name") or "Someone")
        project = escape(p.get("project_name", "a project"))
        with st.container(key=f"rr-row-mark-inv-{n['id']}"):
            text, actions = st.columns([3, 1.4], vertical_alignment="center")
            text.html(
                f"<div class='rr-title'>{project}</div>"
                f"<div class='rr-sub'>{who} invited you as <b>{escape(label(p.get('role')))}</b> · {ui.ago(n['created_at'])}</div>"
            )
            with actions, st.container(horizontal=True, horizontal_alignment="right"):
                if st.button("Decline", key=f"dec_{n['id']}"):
                    ui.answer_invitation(n["invitation_id"], "decline")
                if st.button("Accept", key=f"acc_{n['id']}", type="primary", icon=":material/check:"):
                    ui.answer_invitation(n["invitation_id"], "accept")

# Projects ---------------------------------------------------------------------------
if pending and projects:
    ui.section("Your projects")
elif projects:
    st.space("small")

if not projects:
    st.html(
        "<div class='rr-empty'><div class='rr-title'>No projects yet</div>"
        "<div class='rr-sub'>Create a project to start collecting reviews, or accept an invitation from a teammate.</div></div>"
    )
    st.stop()

shared = len(projects) - len(owned)
views = {"All": len(projects), "Owned by me": len(owned), "Shared with me": shared}
view = st.segmented_control(
    "Show", list(views), default="All", required=True, label_visibility="collapsed",
    format_func=lambda v: f"{v}  {views[v]}", key="projects_view",
)
shown = {
    "All": projects,
    "Owned by me": owned,
    "Shared with me": [p for p in projects if p["my_role"] != "owner"],
}[view]

if not shown:
    st.html(
        "<div class='rr-empty'><div class='rr-sub'>"
        + ("You don't own any projects. Projects you create are owned by you." if view == "Owned by me"
           else "Nobody has shared a project with you yet.")
        + "</div></div>"
    )

for p in shown:
    with st.container(key=f"rr-row-{p['id']}"):
        main, role = st.columns([5, 1], vertical_alignment="center")
        with main, st.container(gap=None):
            with st.container(key=f"rr-open-{p['id']}"):
                if st.button(p["name"], type="tertiary"):
                    ui.open_project(p["id"])
            st.html(
                f"<div class='rr-sub'>{escape(p['description'])}</div>" if p["description"]
                else f"<div class='rr-sub'>Created {ui.nice_date(p['created_at'])}</div>"
            )
        role.html(f"<div style='text-align:right'>{ui.role_text(p['my_role'])}</div>")
