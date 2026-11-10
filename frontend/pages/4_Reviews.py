"""Reviews of a project: import a CSV file, add a review by hand, see the latest ones and past imports."""
from datetime import date
from html import escape

import streamlit as st

import api_client
import ui

WRITERS = ("owner", "analyst")  # same roles as the API's `reviews.write` permission
LATEST = 50
RATINGS = [None, 5, 4, 3, 2, 1]
EXAMPLE_CSV = 'content,rating,author,date,external_id\n"Great app, very easy to use!",5,Maria,2026-11-01,r-1\n'

ui.page("Reviews")
ui.top_bar("projects")

project_id = st.session_state.get("project_id")
if project_id is None:
    st.html("<div class='rr-empty'><div class='rr-title'>No project selected</div>"
            "<div class='rr-sub'>Choose a project from your list.</div></div>")
    st.page_link("pages/1_Projects.py", label="Go to projects", icon=":material/arrow_back:")
    st.stop()

try:
    project = api_client.get(f"/projects/{project_id}")
    reviews = api_client.get(f"/projects/{project_id}/reviews?limit={LATEST}")
    imports = api_client.get(f"/projects/{project_id}/imports")
    categories = api_client.get(f"/projects/{project_id}/categories")
except api_client.ApiError as e:
    st.error(e.detail)
    st.page_link("pages/1_Projects.py", label="Back to projects", icon=":material/arrow_back:")
    st.stop()

archived = project["archived_at"] is not None
can_write = project["my_role"] in WRITERS and not archived
category_names = {c["id"]: c["name"] for c in categories}

# Clear the "Add review" form after a review was added (widget values can only be set before they are drawn).
if st.session_state.pop("reset_review_form", False):
    st.session_state.review_content = ""
    st.session_state.review_author = ""
    st.session_state.review_rating = None
    st.session_state.review_date = None
    st.session_state.review_category = None


def rating_text(rating: int) -> str:
    return "★" * rating + "☆" * (5 - rating)


def problems_table(errors: list[dict]) -> None:
    st.dataframe(
        [{"Row": e["row_number"], "Column": e["field"] or "", "Problem": e["message"]} for e in errors],
        hide_index=True, width="stretch",
    )


def result_summary(result: dict) -> str:
    parts = [f"<b>{result['imported_rows']}</b> imported"]
    if result["duplicate_rows"]:
        parts.append(f"<b>{result['duplicate_rows']}</b> skipped as duplicates")
    if result["invalid_rows"]:
        parts.append(f"<b style='color:var(--pencil)'>{result['invalid_rows']}</b> with problems")
    return " · ".join(parts)


@st.dialog("Rows that could not be imported", width="large")
def problems_dialog(import_id: int) -> None:
    try:
        detail = api_client.get(f"/projects/{project_id}/imports/{import_id}")
    except api_client.ApiError as e:
        st.error(e.detail)
        return
    problems_table(detail["errors"])
    try:
        report = api_client.download(f"/projects/{project_id}/imports/{import_id}/errors.csv")
    except api_client.ApiError as e:
        st.error(e.detail)
    else:
        st.download_button(
            "Download as CSV", report, f"import-{import_id}-problems.csv", "text/csv", icon=":material/download:",
        )
    if detail["invalid_rows"] > len({e["row_number"] for e in detail["errors"]}):
        st.caption("Only the first problems are listed. Fix these and import the file again to see the rest.")


@st.dialog("Rows skipped as duplicates", width="large")
def duplicates_dialog(rows: list[dict], total: int) -> None:
    def where(d: dict) -> str:
        if d["of_review_id"] is not None:
            return f"Already in the project (review #{d['of_review_id']})"
        return f"Same as row {d['of_row']} of this file"

    st.dataframe(
        [{"Row": d["row_number"], "Review": d["content"], "Why": where(d)} for d in rows],
        hide_index=True, width="stretch",
    )
    if total > len(rows):
        st.caption(f"Only the first {len(rows)} of {total} are listed.")


def add_review_form() -> None:
    """Only the text is required."""
    with st.form("add_review", border=False):
        content = st.text_area(
            "Review", key="review_content", height=140, max_chars=10_000, placeholder="What did the customer say?"
        )
        rating = st.selectbox(
            "Rating", RATINGS, key="review_rating", format_func=lambda r: "No rating" if r is None else f"{r} / 5"
        )
        author = st.text_input("Author", key="review_author", max_chars=120, placeholder="Optional")
        written = st.date_input("Date of the review", value=None, key="review_date", max_value=date.today())
        category_id = st.selectbox(
            "Category", [None, *category_names], key="review_category",
            format_func=lambda c: "No category" if c is None else category_names[c],
        )
        if st.form_submit_button("Add review", type="primary", width="stretch"):
            if not content.strip():
                st.warning("Write the review text first.")
                return
            payload = {
                "content": content.strip(),
                "rating": rating,
                "author": author.strip() or None,
                "reviewed_at": written.isoformat() if written else None,
                "category_id": category_id,
            }
            try:
                api_client.post(f"/projects/{project_id}/reviews", payload)
            except api_client.ApiError as e:
                st.error(e.detail)  # e.g. "A review with the same content already exists in this project"
            else:
                st.session_state.reset_review_form = True
                st.session_state.flash = "Review added"
                st.rerun()


# Head ------------------------------------------------------------------------------------
ui.flash()
st.page_link("pages/2_Project.py", label=project["name"], icon=":material/arrow_back:")
left, right = st.columns([3, 1.3], vertical_alignment="bottom")
with left:
    if archived:
        meta = "<b style='color:var(--pencil)'>Archived</b> · reviews can no longer be added"
    elif can_write:
        meta = "Import a CSV file or add a review by hand."
    else:
        meta = f"Your role: <b>{escape(project['my_role'].replace('_', ' ').title())}</b> · only owners and analysts add reviews"
    ui.head("Reviews", meta)
if can_write:
    with right, st.popover("Add review", type="primary", icon=":material/add:", width="stretch"):
        add_review_form()

# The outcome of the last import stays on top, whichever tab is open.
last = st.session_state.get("last_import")
if last:
    with st.container(key="rr-row-mark-last-import"):
        text, act = st.columns([5, 1.4], vertical_alignment="center")
        text.html(
            f"<div class='rr-title'>{escape(last['file_name'])}</div><div class='rr-sub'>{result_summary(last)}</div>"
        )
        with act, st.container(horizontal=True, horizontal_alignment="right"):
            if last["invalid_rows"] and st.button("View problems", key="last_problems", type="tertiary"):
                problems_dialog(last["id"])
            if last.get("duplicates") and st.button("View duplicates", key="last_duplicates", type="tertiary"):
                duplicates_dialog(last["duplicates"], last["duplicate_rows"])
            if st.button("Dismiss", key="last_dismiss", type="tertiary"):
                del st.session_state["last_import"]
                st.rerun()
    if last.get("repeat_of"):
        st.warning(f"This exact file was already imported before (import #{last['repeat_of']}).")
    if last["invalid_rows"]:
        st.caption("The valid rows were imported. Fix the others and upload the file again: reviews already in the project are skipped.")

# Tabs ----------------------------------------------------------------------------------------
tab_names = (["Import CSV"] if can_write else []) + ["Latest reviews", "History"]
tabs = dict(zip(tab_names, st.tabs(tab_names)))

if can_write:
    with tabs["Import CSV"]:
        st.markdown(
            "One review per row, with a header row. Only **content** is required. Other columns: "
            "**rating** (1 to 5), **author**, **date** (like 2026-11-01) and **external_id**.  \n"
            "The file must be UTF-8 (in Excel: *Save as, CSV UTF-8*), up to 2 MB, separated by commas, "
            "semicolons or tabs. Reviews that are already in the project are skipped."
        )
        st.download_button("Download an example file", EXAMPLE_CSV, "reviews-example.csv", "text/csv", type="tertiary",
                           icon=":material/download:")
        chosen = st.file_uploader("CSV file", type="csv", key=f"csv_file_{st.session_state.get('csv_nonce', 0)}")
        if st.button("Import reviews", type="primary", icon=":material/upload_file:", disabled=chosen is None):
            try:
                result = api_client.upload(f"/projects/{project_id}/imports", chosen.name, chosen.getvalue())
            except api_client.ApiError as e:
                st.error(e.detail)  # the file itself cannot be used; it stays selected so it can be swapped
            else:
                st.session_state.last_import = result
                st.session_state.csv_nonce = st.session_state.get("csv_nonce", 0) + 1  # empties the uploader
                st.session_state.flash = f"Imported {result['imported_rows']} reviews"
                st.rerun()

with tabs["Latest reviews"]:
    if not reviews:
        hint = "Use <b>Add review</b> or import a CSV file." if can_write else "Nothing has been added yet."
        st.html(f"<div class='rr-empty'><div class='rr-title'>No reviews yet</div><div class='rr-sub'>{hint}</div></div>")
    for r in reviews:
        details = []
        if r["rating"]:
            details.append(f"<span aria-label='{r['rating']} out of 5'>{rating_text(r['rating'])}</span>")
        if r["author"]:
            details.append(escape(r["author"]))
        if r["reviewed_at"]:
            details.append(ui.nice_date(r["reviewed_at"]))
        if r["category_id"] in category_names:
            details.append(escape(category_names[r["category_id"]]))
        details.append("From a CSV file" if r["source"] == "csv" else "Added by hand")
        with st.container(key=f"rr-row-r-{r['id']}"):
            st.html(
                "<div class='rr-line' style='display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;"
                f"overflow:hidden;white-space:pre-wrap'>{escape(r['content'])}</div>"
                f"<div class='rr-sub'>{' · '.join(details)}</div>"
            )
    if len(reviews) == LATEST:
        st.caption(f"Showing the latest {LATEST} reviews.")

with tabs["History"]:
    if not imports:
        st.html("<div class='rr-empty'><div class='rr-title'>No imports yet</div>"
                "<div class='rr-sub'>Every CSV file you import is listed here.</div></div>")
    for i in imports:
        with st.container(key=f"rr-row-i-{i['id']}"):
            info, act = st.columns([5, 1.6], vertical_alignment="center")
            info.html(
                f"<div class='rr-line'><b>{escape(i['file_name'])}</b></div>"
                f"<div class='rr-sub'>{ui.ago(i['created_at'])} · {result_summary(i)}"
                + (f" · same file as import #{i['repeat_of']}" if i.get("repeat_of") else "")
                + "</div>"
            )
            if i["invalid_rows"]:
                with act, st.container(horizontal=True, horizontal_alignment="right"):
                    if st.button("View problems", key=f"problems_{i['id']}", type="tertiary"):
                        problems_dialog(i["id"])
