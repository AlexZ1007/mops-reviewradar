import streamlit as st

import api_client
import auth

st.set_page_config(page_title="ReviewRadar", page_icon="📡")
st.title("ReviewRadar")

if auth.access_token():
    try:
        me = api_client.get("/me")
    except api_client.ApiError as e:
        st.error(e.detail)
        st.stop()
    st.write(f"Signed in as **{me['email']}**")
    col1, col2 = st.columns(2)
    if col1.button("Go to projects", type="primary"):
        st.switch_page("pages/1_Projects.py")
    if col2.button("Sign out"):
        auth.sign_out()
        st.rerun()
    st.stop()

sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Sign up"])

with sign_in_tab:
    with st.form("sign_in"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", type="primary"):
            error = auth.sign_in(email.strip(), password)
            if error:
                st.error(error)
            else:
                st.switch_page("pages/1_Projects.py")

with sign_up_tab:
    with st.form("sign_up"):
        full_name = st.text_input("Full name")
        email = st.text_input("Email", key="su_email")
        password = st.text_input("Password", type="password", key="su_pw", help="At least 8 characters, letters and digits")
        if st.form_submit_button("Create account", type="primary"):
            error = auth.sign_up(email.strip(), password, full_name.strip())
            if error:
                st.error(error)
            else:
                st.switch_page("pages/1_Projects.py")
