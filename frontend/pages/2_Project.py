import streamlit as st

import api_client
import auth

ROLES = ["owner", "analyst", "product_manager", "viewer"]

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

can_manage = project["my_role"] == "owner" or me["is_admin"]
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
        st.toast(f"Role changed to {st.session_state[key]}")
    except api_client.ApiError as e:
        st.session_state[key] = old_role  # put the dropdown back
        st.session_state.flash_error = e.detail


if "flash_error" in st.session_state:
    st.error(st.session_state.pop("flash_error"))


if st.button("← Projects"):
    st.switch_page("pages/1_Projects.py")

st.title(project["name"])
st.write(project["description"] or "")
st.caption(f"Your role: {project['my_role'] or 'admin (not a member)'}" + (" · archived" if archived else ""))

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
        role = c2.selectbox("Role", ROLES, index=3)
        if c3.form_submit_button("Add"):
            run(lambda: api_client.post(f"/projects/{project_id}/members", {"email": email, "role": role}), f"Added {email}")

for m in members:
    is_me = m["user_id"] == me["id"]
    label = f"{m['full_name'] or m['email']}" + (" (you)" if is_me else "")
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="center")
        c1.markdown(f"**{label}**  \n{m['email']}")
        if can_manage and not archived:
            key = f"role_{m['user_id']}"
            st.session_state[key] = m["role"]  # always show the server's value
            c2.selectbox(
                "Role", ROLES, key=key, label_visibility="collapsed",
                on_change=on_role_change, args=(m["user_id"], m["role"]),
            )
            if c3.button("Remove", key=f"rm_{m['user_id']}"):
                run(lambda: api_client.delete(f"/projects/{project_id}/members/{m['user_id']}"), "Member removed")
        else:
            c2.write(m["role"])
            if is_me and not archived and c3.button("Leave", key="leave"):
                try:
                    api_client.delete(f"/projects/{project_id}/members/{m['user_id']}")
                    st.session_state.pop("project_id", None)
                    st.switch_page("pages/1_Projects.py")
                except api_client.ApiError as e:
                    st.error(e.detail)
