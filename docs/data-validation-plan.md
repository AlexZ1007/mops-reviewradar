# ReviewRadar – Data Validation & Import Plan

Status: **proposed**, not implemented. Covers the two Trello stories below, planned for the next Sprint.

Requirements covered: FR03, FR04, NFR02, NFR04.

| Story | Title | SP |
|-------|-------|----|
| A | As a user, I want to import reviews from CSV so I can analyze feedback in bulk. | 5 |
| B | As a user, I want exact duplicate reviews to be detected so I can avoid counting them. | 3 |

Story B depends on the `reviews` table created by story A.

## Open decisions (to confirm with the Product Owner)

1. **CSV format.** Proposed minimum: `text` (required), `rating` (optional, integer 1–5), `date` (optional, ISO 8601). Unknown columns are ignored.
2. **Hash normalization.** `content_hash` = SHA-256 of the review text. Proposed normalization: strip leading/trailing whitespace only, so "exact" means exact. Case and inner whitespace are kept as-is. Changing this later means recomputing hashes.
3. **Duplicate handling.** Duplicates are skipped, not overwritten. The first occurrence is kept.

## Story A – CSV import

### Acceptance criteria

- An owner or analyst can upload a CSV to an active project.
- Each invalid row is reported with its row number, field name and reason. Valid rows are saved.
- A file missing the required `text` column is rejected as a whole, with a clear message.
- Viewers, product managers and archived projects cannot import (`reviews.write`).
- Re-importing the same file creates no new reviews (see story B).

### Technical plan

1. **Migration** (`supabase migration new reviews_import`): create `imports`, `reviews` and `import_errors`, following `docs/database/erd.md`.
2. **Backend module** `backend/app/imports/`, same layout as `categories/`:
   - `parser.py`: reads the CSV and validates each row. Pure functions, no database access.
   - `service.py`: inserts the import, its reviews and its errors in one transaction.
   - `router.py`:
     - `POST /projects/{project_id}/imports` (multipart upload)
     - `GET /projects/{project_id}/imports/{import_id}`
3. **Permissions:** `has_permission(role, "reviews.write")`, and reject archived projects.
4. **Frontend:** a Streamlit page with `st.file_uploader` and a summary: rows saved, duplicates skipped, errors per row.
5. **Tests:** `backend/tests/test_imports.py`.
   - Parser and validation rules: TDD.
   - Endpoints: API tests following the existing test pattern.

## Story B – Exact duplicate detection

### Acceptance criteria

- Two reviews with the same text in the same project are not saved twice.
- Duplicates within one file and duplicates of existing reviews are handled the same way.
- Re-importing the same file adds nothing and reports the number of duplicates.
- Reviews in another project are not treated as duplicates.

### Technical plan

1. **`content_hash`** column on `reviews`, computed from the normalized text (decision 2).
2. **Database constraint:** `UNIQUE (project_id, content_hash)`. Inserts use `ON CONFLICT DO NOTHING`, so the check is atomic and does not depend on Python code.
3. **Reporting:** the import service counts inserted rows and skipped duplicates, and returns both to the user.
4. **Optional:** `imports.file_sha256`, used to show a warning when the same file is uploaded again. The warning does not block the import.
5. **Tests:** one test per acceptance criterion, plus a test for duplicates inside one file.

## Process

- Story A is large. It is split into (1) parsing and validation and (2) persistence and reporting, so each part can be reviewed on its own.
- Each story is reviewed in a pull request by a developer other than its author.
- The Trello card is moved to *Done* and linked to the pull request.
