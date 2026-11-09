import re
from html import escape
from urllib.parse import urlencode

import streamlit as st

import api_client
import ui
from roles import ROLES, label

ROLE_HELP = {
    "owner": "Manages the project, its members and roles",
    "analyst": "Imports and labels reviews, runs analysis",
    "product_manager": "Tracks recurring issues and exports results",
    "viewer": "Reads reviews and the dashboard",
}

ui.page("Project")
ui.top_bar("projects")

project_id = st.session_state.get("project_id")
if project_id is None:
    st.html("<div class='rr-empty'><div class='rr-title'>No project selected</div>"
            "<div class='rr-sub'>Choose a project from your list.</div></div>")
    st.page_link("pages/1_Projects.py", label="Go to projects", icon=":material/arrow_back:")
    st.stop()

try:
    me = ui.me()
    project = api_client.get(f"/projects/{project_id}")
    members = api_client.get(f"/projects/{project_id}/members")
    category_filter = (st.session_state.get("cat_q") or "").strip()
    categories = api_client.get(
        f"/projects/{project_id}/categories" + (f"?{urlencode({'q': category_filter})}" if category_filter else "")
    )
    can_manage = project["my_role"] == "owner"
    archived = project["archived_at"] is not None
    invitations = api_client.get(f"/projects/{project_id}/invitations") if can_manage and not archived else []
except api_client.ApiError as e:
    st.error(e.detail)
    st.page_link("pages/1_Projects.py", label="Back to projects", icon=":material/arrow_back:")
    st.stop()

editable = can_manage and not archived
open_invites = [i for i in invitations if i["status"] == "pending"]


def run(call, success: str) -> None:
    try:
        call()
    except api_client.ApiError as e:
        st.session_state.flash_error = e.detail
    else:
        st.session_state.flash = success
    st.rerun()


def on_role_change(user_id: str, old_role: str) -> None:
    key = f"role_{user_id}"
    try:
        api_client.patch(f"/projects/{project_id}/members/{user_id}", {"role": st.session_state[key]})
        st.session_state.flash = f"Role changed to {label(st.session_state[key])}"
    except api_client.ApiError as e:
        st.session_state[key] = old_role  # put the dropdown back
        st.session_state.flash_error = e.detail


def display_name(m: dict) -> str:
    return m["full_name"] or m["email"]


ui.flash()

# Head -------------------------------------------------------------------------------
st.page_link("pages/1_Projects.py", label="Projects", icon=":material/arrow_back:")
left, right = st.columns([3, 1.3], vertical_alignment="bottom")
with left:
    facts = [f"Your role: <b>{escape(label(project['my_role']))}</b>",
             f"<span class='rr-num'>{len(members)}</span> member{'s' if len(members) != 1 else ''}",
             f"created {ui.nice_date(project['created_at'])}"]
    if archived:
        facts.insert(0, "<b style='color:var(--pencil)'>Archived</b>")
    ui.head(project["name"], " · ".join(facts))

if st.session_state.pop("reset_invite", False):
    st.session_state.invite_emails = ""

with right, st.container(horizontal=True, horizontal_alignment="right"):
    if editable:
        with st.popover("Invite people", type="primary", icon=":material/person_add:"):
            with st.form("invite_member", border=False):
                raw = st.text_area(
                    "Email addresses", key="invite_emails", height=80,
                    placeholder="maria@company.com, andrei@company.com",
                    help="Separate several addresses with commas or new lines",
                )
                role = st.radio(
                    "Role in this project", ROLES, index=ROLES.index("viewer"), format_func=label,
                    captions=[ROLE_HELP[r] for r in ROLES],
                )
                st.caption("Invitations expire after 7 days.")
                if st.form_submit_button("Send invitations", type="primary", icon=":material/send:", width="stretch"):
                    emails = [e for e in re.split(r"[\s,;]+", raw.strip()) if e]
                    if not emails:
                        st.warning("Enter at least one email address.")
                    else:
                        sent, failed = [], []
                        for email in dict.fromkeys(emails):
                            try:
                                api_client.post(f"/projects/{project_id}/invitations", {"email": email, "role": role})
                                sent.append(email)
                            except api_client.ApiError as e:
                                reason = e.detail if e.status in (409, 422) else "couldn't be sent, try again"
                                failed.append(f"**{email}**: {reason}")
                        if failed and not sent:
                            st.error("  \n".join(failed))
                        elif failed:
                            # Some went out: refresh the list, keep the failures on screen after the rerun.
                            st.session_state.flash = f"Sent to {', '.join(sent)}"
                            st.session_state.flash_error = "Not sent:  \n" + "  \n".join(failed)
                            st.rerun()
                        else:
                            st.session_state.reset_invite = True
                            who = sent[0] if len(sent) == 1 else f"{len(sent)} people"
                            st.session_state.flash = f"Invitation sent to {who} as {label(role)}"
                            st.rerun()

if project["description"]:
    st.html(f"<p class='rr-sub' style='-webkit-line-clamp:unset;margin-top:.25rem'>{escape(project['description'])}</p>")


@st.dialog("Leave this project?")
def leave_dialog() -> None:
    others = [m for m in members if m["user_id"] != me["id"]]
    owners = [m for m in members if m["role"] == "owner"]
    if project["my_role"] == "owner" and len(owners) == 1:
        if not others:
            st.warning("You are the only member. Archive the project from Settings instead of leaving it.")
            return
        # Same rule as the API: the member who joined first becomes owner.
        successor = min(others, key=lambda m: (m["joined_at"], m["user_id"]))
        st.write(
            f"You are the last owner. **{display_name(successor)}** ({successor['email']}) has been a member "
            "the longest and will become the owner."
        )
    else:
        st.write(f"You will lose access to **{project['name']}** until someone invites you again.")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Cancel"):
            st.rerun()
        if st.button("Leave project", type="primary"):
            try:
                api_client.delete(f"/projects/{project_id}/members/{me['id']}")
            except api_client.ApiError as e:
                st.error(e.detail)
                return
            st.session_state.pop("project_id", None)
            st.session_state.flash = f"You left {project['name']}"
            st.switch_page("pages/1_Projects.py")


# Tabs -------------------------------------------------------------------------------
st.space("small")
tab_names = [f"Members  {len(members)}", "Categories" if category_filter else f"Categories  {len(categories)}"]
if editable:
    tab_names += [f"Invitations  {len(open_invites)}" if open_invites else "Invitations", "Settings"]
tabs = st.tabs(tab_names)

with tabs[0]:
    # Owners first, then by name.
    order = {r: i for i, r in enumerate(ROLES)}
    for m in sorted(members, key=lambda m: (order.get(m["role"], 9), display_name(m).lower())):
        is_me = m["user_id"] == me["id"]
        with st.container(key=f"rr-row-m-{m['user_id']}"):
            who, role_col, act = st.columns([4, 2, 1.1], vertical_alignment="center")
            who.html(
                "<div style='display:flex;gap:.85rem;align-items:center'>"
                f"{ui.avatar(display_name(m), is_me)}<div><div class='rr-line'><b>{escape(display_name(m))}</b>"
                f"{' <span class=rr-muted>(you)</span>' if is_me else ''}</div>"
                f"<div class='rr-sub'>{escape(m['email'])} · joined {ui.nice_date(m['joined_at'])}</div></div></div>"
            )
            if editable:
                key = f"role_{m['user_id']}"
                st.session_state[key] = m["role"]  # always show the server's value
                role_col.selectbox(
                    f"Role of {display_name(m)}", ROLES, key=key, label_visibility="collapsed", format_func=label,
                    on_change=on_role_change, args=(m["user_id"], m["role"]),
                )
            else:
                role_col.html(ui.role_text(m["role"]))
            if archived:
                continue
            with act, st.container(horizontal=True, horizontal_alignment="right"):
                if is_me:
                    if st.button("Leave", key="leave", type="tertiary", icon=":material/logout:"):
                        leave_dialog()
                elif editable:
                    with st.popover("", icon=":material/more_horiz:", help=f"Manage {display_name(m)}"):
                        st.caption(f"Remove {display_name(m)} from {project['name']}?")
                        if st.button("Remove from project", key=f"rm_{m['user_id']}", icon=":material/person_remove:"):
                            run(lambda: api_client.delete(f"/projects/{project_id}/members/{m['user_id']}"),
                                f"Removed {display_name(m)}")

DEFAULT_CATEGORY_COLOR = "#b0122b"


def category_form(cat: dict | None = None) -> None:
    """Create (cat is None) or edit a category. Name is required; color is optional."""
    with st.form(f"category_{cat['id'] if cat else 'new'}", border=False):
        name = st.text_input("Name", cat["name"] if cat else "", max_chars=80)
        use_color = st.checkbox("Mark with a color", value=bool(cat and cat["color"]))
        color = st.color_picker(
            "Color", (cat and cat["color"]) or DEFAULT_CATEGORY_COLOR, label_visibility="collapsed"
        )
        if st.form_submit_button("Save" if cat else "Create category", type="primary", width="stretch"):
            payload = {"name": name.strip(), "color": color if use_color else None}
            if not payload["name"]:
                st.warning("The category name can't be empty.")
            elif cat:
                run(lambda: api_client.patch(f"/projects/{project_id}/categories/{cat['id']}", payload),
                    "Category saved")
            else:
                run(lambda: api_client.post(f"/projects/{project_id}/categories", payload),
                    f"Created {payload['name']}")


with tabs[1]:
    find_col, new_col = st.columns([3, 1.3], vertical_alignment="center")
    find_col.text_input(
        "Filter categories", key="cat_q", placeholder="Filter by name", label_visibility="collapsed",
        icon=":material/search:", max_chars=80,
    )
    if editable:
        with new_col, st.popover("New category", type="primary", icon=":material/add:", width="stretch"):
            category_form()
    if not categories:
        if category_filter:
            title, hint = "No matching categories", "Try a different name."
        elif editable:
            title, hint = "No categories yet", "Use <b>New category</b> to group reviews your own way."
        else:
            title, hint = "No categories yet", "The project owner hasn't set any up."
        st.html(f"<div class='rr-empty'><div class='rr-title'>{title}</div><div class='rr-sub'>{hint}</div></div>")
    for c in categories:
        with st.container(key=f"rr-row-c-{c['id']}"):
            info, act = st.columns([6, 1.1], vertical_alignment="center")
            dot = (f"<span style='display:inline-block;width:.8rem;height:.8rem;border-radius:50%;"
                   f"background:{escape(c['color'])};margin-right:.65rem'></span>") if c["color"] else ""
            info.html(f"<div class='rr-line'>{dot}<b>{escape(c['name'])}</b></div>")
            if editable:
                with act, st.container(horizontal=True, horizontal_alignment="right"):
                    with st.popover("", icon=":material/edit:", help=f"Edit {c['name']}"):
                        category_form(c)
                        st.caption("Reviews filed under it become uncategorized if you delete it.")
                        if st.button("Delete category", key=f"cat_del_{c['id']}", icon=":material/delete:"):
                            run(lambda: api_client.delete(f"/projects/{project_id}/categories/{c['id']}"),
                                f"Deleted {c['name']}")

if editable:
    with tabs[2]:
        if not invitations:
            st.html("<div class='rr-empty'><div class='rr-title'>No open invitations</div>"
                    "<div class='rr-sub'>Use <b>Invite people</b> to add teammates by email.</div></div>")
        for inv in invitations:
            expired = inv["status"] == "expired"
            with st.container(key=f"rr-row-i-{inv['id']}"):
                who, role_col, act = st.columns([4, 2, 1.1], vertical_alignment="center")
                when = "Expired" if expired else ui.until(inv["expires_at"])
                who.html(
                    f"<div class='rr-line'><b>{escape(inv['email'])}</b></div>"
                    f"<div class='rr-sub'>Invited by {escape(inv['invited_by_name'] or 'unknown')} · {ui.ago(inv['created_at'])}"
                    f" · <span style='{'color:var(--pencil)' if expired else ''}'>{when}</span></div>"
                )
                role_col.html(ui.role_text(inv["role"]))
                with act, st.container(horizontal=True, horizontal_alignment="right"):
                    if st.button("Revoke", key=f"revoke_{inv['id']}", type="tertiary"):
                        run(lambda: api_client.delete(f"/projects/{project_id}/invitations/{inv['id']}"),
                            f"Invitation to {inv['email']} revoked")

    with tabs[3]:
        with st.form("edit_project", border=False):
            name = st.text_input("Project name", project["name"], max_chars=120)
            description = st.text_area("Description", project["description"] or "", height=110)
            if st.form_submit_button("Save changes", type="primary"):
                if not name.strip():
                    st.warning("The project name can't be empty.")
                else:
                    run(lambda: api_client.patch(
                        f"/projects/{project_id}", {"name": name.strip(), "description": description.strip()}
                    ), "Project saved")

        st.html("<div class='rr-danger'><div class='rr-title'>Archive project</div>"
                "<div class='rr-sub'>Archived projects disappear from everyone's list and can no longer be edited.</div></div>")
        confirm = st.checkbox(f"I understand that members lose access to {project['name']}")
        if st.button("Archive project", icon=":material/inventory_2:", disabled=not confirm):
            try:
                api_client.delete(f"/projects/{project_id}")
            except api_client.ApiError as e:
                st.error(e.detail)
            else:
                st.session_state.pop("project_id", None)
                st.session_state.flash = f"Archived {project['name']}"
                st.switch_page("pages/1_Projects.py")
