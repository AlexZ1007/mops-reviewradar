import streamlit as st

import api_client
import auth
from roles import ROLES, label

st.set_page_config(page_title="Project · ReviewRadar", page_icon="📡")
auth.require_login()

project_id = st.session_state.get("project_id")
if project_id is None:
    st.info("Pick a project first.")
    if st.button("Back to projects"):
        st.switch_page("pages/1_Projects.py")
    st.stop()

try:
    me = api_client.get("/me")
    project = api_client.get(f"/projects/{project_id}")
    members = api_client.get(f"/projects/{project_id}/members")
except api_client.ApiError as e:
    st.error(e.detail)
    st.stop()

can_manage = project["my_role"] == "owner"
archived = project["archived_at"] is not None


def run(call, success: str) -> None:
    try:
        call()
        st.toast(success)
        st.rerun()
    except api_client.ApiError as e:
        st.error(e.detail)


def on_role_change(user_id: str, old_role: str) -> None:
    key = f"role_{user_id}"
    try:
        api_client.patch(f"/projects/{project_id}/members/{user_id}", {"role": st.session_state[key]})
        st.toast(f"Role changed to {label(st.session_state[key])}")
    except api_client.ApiError as e:
        st.session_state[key] = old_role  # put the dropdown back
        st.session_state.flash_error = e.detail


if "flash_error" in st.session_state:
    st.error(st.session_state.pop("flash_error"))


if st.button("← Projects"):
    st.switch_page("pages/1_Projects.py")

st.title(project["name"])
st.write(project["description"] or "")
st.caption(f"Your role: {label(project['my_role'])}" + (" · archived" if archived else ""))

# Project settings (owner) -------------------------------------------------------
if can_manage and not archived:
    with st.expander("Project settings"):
        with st.form("edit_project"):
            name = st.text_input("Name", project["name"])
            description = st.text_area("Description", project["description"] or "")
            if st.form_submit_button("Save"):
                run(lambda: api_client.patch(f"/projects/{project_id}", {"name": name, "description": description}), "Saved")
        if st.button("Archive project", type="secondary"):
            try:
                api_client.delete(f"/projects/{project_id}")
                st.session_state.pop("project_id", None)
                st.switch_page("pages/1_Projects.py")
            except api_client.ApiError as e:
                st.error(e.detail)

# Members ----------------------------------------------------------------------
st.subheader("Members")

if can_manage and not archived:
    with st.form("add_member", clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="bottom")
        email = c1.text_input("Email of a registered user")
        role = c2.selectbox("Role", ROLES, index=3, format_func=label)
        if c3.form_submit_button("Add"):
            try:
                api_client.post(f"/projects/{project_id}/members", {"email": email.strip(), "role": role})
                st.toast(f"Added {email.strip()}")
                st.rerun()
            except api_client.ApiError as e:
                # Don't reveal whether an email has an account.
                st.error(e.detail if e.status == 409 else "Couldn't add this person. Check the email address and try again.")

def display_name(m: dict) -> str:
    return m["full_name"] or m["email"]


@st.dialog("Leave project?")
def leave_dialog() -> None:
    others = [m for m in members if m["user_id"] != me["id"]]
    owners = [m for m in members if m["role"] == "owner"]
    if project["my_role"] == "owner" and len(owners) == 1:
        if not others:
            st.warning("You are the only member of this project. Archive it instead of leaving.")
            return
        # Same rule as the API: the member who joined first becomes owner.
        successor = min(others, key=lambda m: (m["joined_at"], m["user_id"]))
        st.warning(
            f"You are the last owner. **{display_name(successor)}** ({successor['email']}) joined the project "
            "first and will become the owner when you leave."
        )
    else:
        st.write("You will lose access to this project.")
    if st.button("Leave project", type="primary"):
        try:
            api_client.delete(f"/projects/{project_id}/members/{me['id']}")
        except api_client.ApiError as e:
            st.error(e.detail)
            return
        st.session_state.pop("project_id", None)
        st.switch_page("pages/1_Projects.py")


for m in members:
    is_me = m["user_id"] == me["id"]
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="center")
        c1.markdown(f"**{display_name(m)}**" + (" (you)" if is_me else "") + f"  \n{m['email']}")
        if can_manage and not archived:
            key = f"role_{m['user_id']}"
            st.session_state[key] = m["role"]  # always show the server's value
            c2.selectbox(
                "Role", ROLES, key=key, label_visibility="collapsed", format_func=label,
                on_change=on_role_change, args=(m["user_id"], m["role"]),
            )
        else:
            c2.write(label(m["role"]))
        if archived:
            continue
        if is_me:
            if c3.button("Leave", key="leave"):
                leave_dialog()
        elif can_manage and c3.button("Remove", key=f"rm_{m['user_id']}"):
            run(lambda: api_client.delete(f"/projects/{project_id}/members/{m['user_id']}"), "Member removed")
