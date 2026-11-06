import streamlit as st

import auth
import ui

st.set_page_config(page_title="Sign in · ReviewRadar", page_icon=":material/radar:", layout="centered")
ui.styles()

if auth.access_token():
    st.switch_page("pages/1_Projects.py")

st.html(
    """
<style>
  .block-container, [data-testid="stMainBlockContainer"] { max-width: 920px; padding-top: 12vh; }
  .rr-intro h1 { font-family: var(--serif) !important; font-size: 2.6rem !important; line-height: 1.1; font-weight: 600; margin: 2.5rem 0 1rem; letter-spacing: -0.02em; }
  .rr-intro p { color: var(--graphite); font-size: 1.02rem; line-height: 1.55; max-width: 34ch; margin: 0; }
  .rr-intro ul { list-style: none; padding: 0; margin: 2rem 0 0; color: var(--ink); }
  .rr-intro li { padding: .55rem 0; border-top: 1px solid var(--rule); font-size: .95rem; }
  .st-key-rr-auth { padding-top: 2.2rem; }
  @media (max-width: 640px) { .block-container, [data-testid="stMainBlockContainer"] { padding-top: 2rem; } .rr-intro h1 { font-size: 2rem; } }
</style>
"""
)

intro, form_col = st.columns([1.05, 1], gap="large")

with intro:
    st.html(
        f"""
<div class="rr-intro">
  <div class="rr-wordmark">{ui.LOGO}<span>ReviewRadar</span></div>
  <h1>What are customers telling you?</h1>
  <p>Collect product reviews into projects, read the sentiment, and give each teammate the access their role needs.</p>
  <ul><li>Owners manage members and roles</li><li>Analysts import and label reviews</li><li>Product managers track recurring issues</li></ul>
</div>"""
    )

with form_col, st.container(key="rr-auth"):
    mode = st.segmented_control(
        "Account", ["Sign in", "Create account"], default="Sign in", required=True, label_visibility="collapsed",
        width="stretch",
    )
    if mode == "Sign in":
        with st.form("sign_in", border=False):
            email = st.text_input("Email", autocomplete="email")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            if st.form_submit_button("Sign in", type="primary", width="stretch"):
                if not email.strip() or not password:
                    st.warning("Enter your email and password.")
                elif error := auth.sign_in(email.strip(), password):
                    st.error(error)
                else:
                    st.switch_page("pages/1_Projects.py")
    else:
        with st.form("sign_up", border=False):
            full_name = st.text_input("Full name", autocomplete="name")
            email = st.text_input("Work email", key="su_email", autocomplete="email")
            password = st.text_input(
                "Password", type="password", key="su_pw", autocomplete="new-password",
                help="At least 8 characters, with letters and digits",
            )
            if st.form_submit_button("Create account", type="primary", width="stretch"):
                if not full_name.strip() or not email.strip() or not password:
                    st.warning("Fill in your full name, email and password.")
                elif error := auth.sign_up(email.strip(), password, full_name.strip()):
                    st.error(error)
                else:
                    st.switch_page("pages/1_Projects.py")
