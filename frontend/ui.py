"""Shared look and shell for every ReviewRadar page: styles, top bar, small render helpers."""
from datetime import UTC, datetime
from html import escape

import streamlit as st

import api_client
import auth
from roles import label

PENCIL = "#b0122b"

# A slightly irregular hand-drawn ring, drawn in once. It marks rows that need the visitor's decision.
_RING = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
    "<path d='M13.5 3.2C8 2.6 3.4 6 3.2 11.4c-.2 5 3.6 9.1 8.8 9.4 5 .3 8.9-3.2 8.9-8.4 0-4.6-3.4-8.3-8.2-8.6-1.6-.1-3 .3-4.1.9' "
    "fill='none' stroke='%23b0122b' stroke-width='2.2' stroke-linecap='round'/></svg>"
).replace("<", "%3C").replace(">", "%3E")  # keep "</style>" from closing the page's own <style> block

CSS = f"""
<style>
:root {{
  --ink: #1a1a1a; --graphite: #5f5b57; --rule: #e7e4e0; --sheet: #ffffff; --tint: #f6f5f3;
  --pencil: {PENCIL}; --pencil-wash: #f8e4e7;
  --serif: "Source Serif 4", Georgia, serif;
}}
::selection {{ background: var(--pencil-wash); color: var(--ink); }}
html {{ scrollbar-color: #cfcac5 transparent; caret-color: var(--pencil); }}
:focus-visible {{ outline: 2px solid var(--pencil) !important; outline-offset: 2px; }}
header[data-testid="stHeader"] {{ display: none; }}
[data-testid="InputInstructions"] {{ display: none; }}  /* the "Press Enter to submit form" hint */
.block-container, [data-testid="stMainBlockContainer"] {{ max-width: 1040px; padding: 0 2rem 5rem; }}
h1, h2, h3 {{ font-family: var(--serif) !important; letter-spacing: -0.015em; text-wrap: balance; }}
h1 {{ font-size: 2.5rem !important; padding: 0 !important; }}
h3 {{ font-size: 1.15rem !important; padding: 0 !important; }}
[data-testid="stCaptionContainer"], .rr-muted {{ color: var(--graphite) !important; }}
.rr-num {{ font-variant-numeric: tabular-nums; }}

/* Top bar: full-bleed white strip with one hairline under it. */
.st-key-rr-topbar {{
  position: sticky; top: 0; z-index: 50; background: var(--sheet);
  box-shadow: 0 0 0 100vmax var(--sheet); clip-path: inset(0 -100vmax);
  border-bottom: 1px solid var(--rule);
  border-image: linear-gradient(var(--rule), var(--rule)) 0 0 1 0 / 0 0 1px 0 / 0 100vmax;
  min-height: 60px; margin-bottom: 2.5rem; align-items: center !important; gap: 2rem !important;
}}
.rr-wordmark {{ font-weight: 700; font-size: 1.05rem; letter-spacing: -0.01em; color: var(--ink); display: flex; align-items: center; gap: .5rem; white-space: nowrap; }}
.rr-wordmark svg {{ display: block; }}
.st-key-rr-topbar [data-testid="stPageLink"] a {{
  border-radius: 0; padding: 18px 2px 17px; background: transparent !important;
}}
.st-key-rr-topbar [data-testid="stPageLink"] a p {{ font-weight: 500; color: var(--graphite); }}
.st-key-rr-topbar [data-testid="stPageLink"] a:hover p {{ color: var(--ink); }}
[class*="st-key-rr-nav-on"] [data-testid="stPageLink"] a {{ box-shadow: inset 0 -2px 0 var(--pencil); }}
[class*="st-key-rr-nav-on"] [data-testid="stPageLink"] a p {{ color: var(--ink) !important; font-weight: 600; }}
.st-key-rr-topbar > :last-child {{ margin-left: auto; }}
.st-key-rr-account button {{ border: none !important; background: transparent !important; padding-right: 0; }}
.rr-avatar {{
  width: 32px; height: 32px; border-radius: 50%; display: inline-grid; place-items: center; flex: none;
  background: var(--tint); color: var(--ink); font-weight: 600; font-size: .8rem; letter-spacing: .02em;
}}
.rr-avatar.me {{ background: var(--ink); color: #fff; }}

/* Page head: title + one line of facts on the left, the page's main action on the right. */
.rr-meta {{ color: var(--graphite); margin: .35rem 0 0; font-size: .95rem; }}
.rr-meta b {{ color: var(--ink); font-weight: 600; }}
.rr-section {{ font-family: var(--serif); font-size: 1.2rem; font-weight: 600; margin: 2.25rem 0 .25rem; color: var(--ink); }}

/* Ruled rows. Every row leaves a margin on the left; the pencil ring lives there. */
[class*="st-key-rr-row"] {{ border-bottom: 1px solid var(--rule); padding: 14px 18px 14px 30px; position: relative; }}
[class*="st-key-rr-row"]:hover {{ background: linear-gradient(90deg, transparent, var(--tint) 30px); }}
[class*="st-key-rr-row-mark"]::before {{
  content: ""; position: absolute; left: 2px; top: 18px; width: 18px; height: 18px;
  background: url("{_RING}") center / contain no-repeat;
  animation: rr-ring .6s cubic-bezier(.16, 1, .3, 1) .1s both;
}}
/* The pencil circles the item: a sweep that starts where the stroke starts (top right). */
@keyframes rr-ring {{
  from {{ clip-path: polygon(50% 50%, 60% 0, 60% 0, 60% 0, 60% 0, 60% 0, 60% 0); }}
  25% {{ clip-path: polygon(50% 50%, 60% 0, 0 0, 0 0, 0 0, 0 0, 0 0); }}
  50% {{ clip-path: polygon(50% 50%, 60% 0, 0 0, 0 100%, 0 100%, 0 100%, 0 100%); }}
  75% {{ clip-path: polygon(50% 50%, 60% 0, 0 0, 0 100%, 100% 100%, 100% 100%, 100% 100%); }}
  to {{ clip-path: polygon(50% 50%, 60% 0, 0 0, 0 100%, 100% 100%, 100% 0, 60% 0); }}
}}
@media (prefers-reduced-motion: reduce) {{ [class*="st-key-rr-row-mark"]::before {{ animation: none; }} }}
.rr-title {{ font-family: var(--serif); font-size: 1.15rem; font-weight: 600; color: var(--ink); line-height: 1.3; }}
.rr-sub {{ color: var(--graphite); font-size: .92rem; margin-top: 2px; line-height: 1.45; max-width: 62ch;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.rr-line {{ color: var(--ink); line-height: 1.5; }}
.rr-role {{ color: var(--graphite); font-size: .9rem; white-space: nowrap; }}
.rr-role.owner {{ color: var(--ink); font-weight: 600; }}

/* Project names are the link: serif, no button chrome. */
[class*="st-key-rr-open"] button {{ padding: 0 !important; min-height: 0 !important; justify-content: flex-start; }}
[class*="st-key-rr-open"] button p {{ font-family: var(--serif); font-size: 1.15rem; font-weight: 600; color: var(--ink); text-align: left; }}
[class*="st-key-rr-row"]:hover [class*="st-key-rr-open"] button p {{ color: var(--pencil); text-decoration: underline; text-underline-offset: 4px; text-decoration-thickness: 1px; }}
/* The whole row opens the project: the name's button stretches an invisible hit area over the row. */
[class*="st-key-rr-row"]:has([class*="st-key-rr-open"]) {{ cursor: pointer; }}
[class*="st-key-rr-row"]:has([class*="st-key-rr-open"]) :is([data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"],
  [data-testid="stColumn"], [data-testid="stElementContainer"], [data-testid="stButton"], [class*="st-key-rr-open"]) {{ position: static; }}
[class*="st-key-rr-open"] button::after {{ content: ""; position: absolute; inset: 0; z-index: 1; }}

/* Tabs: underline in pencil, no grey bar. */
[data-baseweb="tab-highlight"] {{ background-color: var(--pencil) !important; }}
[data-baseweb="tab-border"] {{ background-color: var(--rule) !important; }}
[data-baseweb="tab"] p {{ font-weight: 500; }}

.rr-empty {{ padding: 3rem 0 2rem 30px; border-bottom: 1px solid var(--rule); }}
.rr-empty .rr-title {{ margin-bottom: .35rem; }}
.rr-danger {{ border-top: 1px solid var(--rule); margin-top: 2.5rem; padding-top: 1.25rem; }}

@media (max-width: 640px) {{
  .block-container, [data-testid="stMainBlockContainer"] {{ padding: 0 1rem 4rem; }}
  .st-key-rr-topbar {{ gap: 1rem !important; }}
  .rr-wordmark span {{ display: none; }}
  h1 {{ font-size: 2rem !important; }}
}}
</style>
"""

_LOGO_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24'>"
    "<circle cx='12' cy='12' r='9.5' fill='none' stroke='#1a1a1a' stroke-width='1.6'/>"
    "<circle cx='12' cy='12' r='5' fill='none' stroke='#1a1a1a' stroke-width='1.6'/>"
    "<path d='M12 12 L19 5' stroke='#b0122b' stroke-width='2' stroke-linecap='round'/>"
    "<circle cx='12' cy='12' r='1.8' fill='#b0122b'/></svg>"
)
# st.html strips inline <svg>, so the mark ships as an image.
LOGO = (
    "<img width='22' height='22' alt='' src=\"data:image/svg+xml;utf8,"
    + _LOGO_SVG.replace("#", "%23").replace("<", "%3C").replace(">", "%3E")
    + '">'
)


def styles() -> None:
    st.html(CSS)


def page(title: str) -> None:
    st.set_page_config(page_title=f"{title} · ReviewRadar", page_icon=":material/radar:", layout="centered")
    styles()


def me() -> dict:
    """The signed-in profile, fetched once per run."""
    if "_me" not in st.session_state:
        st.session_state._me = api_client.get("/me")
    return st.session_state._me


def initials(name: str) -> str:
    parts = [p for p in name.replace("@", " ").replace(".", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def avatar(name: str, mine: bool = False) -> str:
    return f"<span class='rr-avatar{' me' if mine else ''}' aria-hidden='true'>{escape(initials(name))}</span>"


def top_bar(active: str) -> None:
    """White strip on every signed-in page: wordmark, Projects, Inbox (with unread count), account menu."""
    auth.require_login()
    try:
        profile = me()
    except api_client.ApiError as e:
        st.error(e.detail)
        st.stop()
    try:
        unread = api_client.get("/notifications/unread-count")["count"]
    except api_client.ApiError:
        unread = 0  # the inbox count is a convenience; never block the page on it
    name = profile["full_name"] or profile["email"]
    with st.container(key="rr-topbar", horizontal=True, vertical_alignment="center"):
        st.html(f"<div class='rr-wordmark'>{LOGO}<span>ReviewRadar</span></div>", width="content")
        with st.container(key="rr-nav-on-projects" if active == "projects" else "rr-nav-projects", width="content"):
            st.page_link("pages/1_Projects.py", label="Projects")
        with st.container(key="rr-nav-on-inbox" if active == "inbox" else "rr-nav-inbox", width="content"):
            st.page_link("pages/3_Notifications.py", label=f"Inbox · {unread}" if unread else "Inbox")
        with st.container(key="rr-account", width="content"):
            with st.popover(initials(name), help="Account"):
                st.markdown(f"**{escape(name)}**  \n:gray[{escape(profile['email'])}]")
                if st.button("Sign out", icon=":material/logout:", width="stretch"):
                    auth.sign_out()
                    st.switch_page("Home.py")


def flash() -> None:
    """Show messages queued before the last rerun or page switch."""
    if "flash" in st.session_state:
        st.toast(st.session_state.pop("flash"), icon=":material/check_circle:")
    if "flash_error" in st.session_state:
        st.error(st.session_state.pop("flash_error"))


def head(title: str, meta: str = "") -> None:
    st.title(title, anchor=False)
    if meta:
        st.html(f"<p class='rr-meta'>{meta}</p>")


def section(text: str) -> None:
    st.html(f"<div class='rr-section'>{escape(text)}</div>")


def role_text(role: str | None) -> str:
    return f"<span class='rr-role{' owner' if role == 'owner' else ''}'>{escape(label(role))}</span>"


def ago(ts: str) -> str:
    when = datetime.fromisoformat(ts)
    when = when if when.tzinfo else when.replace(tzinfo=UTC)
    seconds = (datetime.now(UTC) - when).total_seconds()
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"


def until(ts: str) -> str:
    when = datetime.fromisoformat(ts)
    when = when if when.tzinfo else when.replace(tzinfo=UTC)
    seconds = (when - datetime.now(UTC)).total_seconds()
    if seconds <= 0:
        return "Expired"
    days, hours = int(seconds // 86400), int(seconds // 3600)
    if days >= 1:
        return f"Expires in {days} day{'s' if days > 1 else ''}"
    return f"Expires in {max(hours, 1)} hour{'s' if hours > 1 else ''}"


def nice_date(ts: str) -> str:
    d = datetime.fromisoformat(ts)
    return f"{d:%b} {d.day}, {d.year}"


def open_project(project_id: int) -> None:
    st.session_state.project_id = project_id
    st.switch_page("pages/2_Project.py")


def answer_invitation(invitation_id: int, action: str) -> None:
    """Accept (then open the project) or decline an invitation."""
    try:
        result = api_client.post(f"/invitations/{invitation_id}/{action}", {})
    except api_client.ApiError as e:
        st.session_state.flash_error = e.detail
        st.rerun()
    if action == "accept":
        st.session_state.flash = f"You joined {result['name']}"
        open_project(result["id"])
    st.session_state.flash = "Invitation declined"
    st.rerun()
