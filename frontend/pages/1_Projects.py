import streamlit as st

import api_client
import auth
from roles import label

st.set_page_config(page_title="Projects · ReviewRadar", page_icon="📡")
auth.require_login()

auth.nav_header()
st.title("Projects")

with st.expander("New project"):
    with st.form("create_project", clear_on_submit=True):
        name = st.text_input("Name")
        description = st.text_area("Description (optional)")
        if st.form_submit_button("Create", type="primary"):
            try:
                api_client.post("/projects", {"name": name, "description": description or None})
                st.success(f"Created {name}")
            except api_client.ApiError as e:
                st.error(e.detail)

try:
    projects = api_client.get("/projects")
except api_client.ApiError as e:
    st.error(e.detail)
    st.stop()

if not projects:
    st.info("You are not a member of any project yet.")

for p in projects:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        left.markdown(f"**{p['name']}**  \n{p['description'] or ''}")
        left.caption(f"Your role: {label(p['my_role'])}")
        if right.button("Open", key=f"open_{p['id']}"):
            st.session_state.project_id = p["id"]
            st.switch_page("pages/2_Project.py")
