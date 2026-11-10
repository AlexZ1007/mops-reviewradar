# ReviewRadar – Data Validation & Import

Status: **implemented on `main`** (PR #3 `feature/review-ingestion`, merged). This document describes what the code does, and records the decisions behind it. It replaces the earlier proposal, which is kept in git history (commit `a5f0971`).

Requirements covered: FR03, FR04, NFR02, NFR04.

| Story | Title | SP | Status |
|-------|-------|----|--------|
| A | As a user, I want to import reviews from CSV so I can analyze feedback in bulk. | 5 | Implemented |
| B | As a user, I want exact duplicate reviews to be detected so I can avoid counting them. | 3 | Implemented |

Story B depends on the `reviews` table created by story A.

## Decisions

1. **CSV format.** Required column: `content` (also accepted as `review`, `text` or `comment`). Optional columns: `rating` (whole number 1–5), `date` (ISO 8601, e.g. `2026-11-01` or `2026-11-01T10:30:00`; no time zone means UTC), `author`, `external_id`. Unknown columns are ignored. The delimiter is detected automatically (comma, semicolon or tab; semicolon is common in Excel with Romanian locale). A UTF-8 BOM is accepted. Files must be UTF-8 and at most 2 MB.
2. **Hash normalization.** `content_hash` is the SHA-256 of the normalized content. Normalization (`backend/app/reviews/hashing.py`):
   - Unicode NFC form
   - runs of whitespace collapsed to one space, and leading/trailing whitespace removed
   - case-insensitive (`casefold()`)

   So "Great app" and "great   APP" are duplicates. Changing this function would change the hashes of stored reviews, so it should not be changed without a migration.
3. **Duplicate handling.** A duplicate is skipped, not overwritten. The first occurrence is kept. Duplicates within one file and duplicates of existing reviews are treated the same way.
4. **Invalid rows do not stop the import.** Valid rows are saved, and each invalid row is reported with its row number, field and reason. A file that cannot be read at all (empty, wrong encoding, no `content` column, not a `.csv`) is rejected and nothing is saved.
5. **Audit.** Each completed import writes an `import.completed` entry to `audit_log`. Rejected files are not audited.

## Story A – CSV import

### Acceptance criteria and where they are met

| Criterion | Where |
|-----------|-------|
| Owner or analyst can import into an active project | `reviews.write` check in `backend/app/imports/service.py`; archived projects are read-only (`test_archived_project_is_read_only`) |
| Invalid rows are reported with row number, field and reason; valid rows are saved | `backend/app/imports/validation.py`; `test_invalid_rows_are_reported_and_valid_rows_still_imported` |
| A file without the required column is rejected as a whole, with a clear message | `backend/app/imports/csv_parser.py`; `test_unreadable_file_is_rejected_and_leaves_no_trace` |
| Viewers, product managers and non-members cannot import | `test_other_roles_can_read_history_but_not_import`, `test_non_member_gets_404` |
| Re-importing the same file creates no new reviews | `test_importing_the_same_file_twice_adds_nothing` |

### Structure

- **Migration** `supabase/migrations/20261110000000_reviews_imports.sql`: tables `imports`, `import_errors` and `reviews`.
- **Backend module** `backend/app/imports/`:
  - `csv_parser.py`: reads the file, detects the delimiter, checks the header.
  - `validation.py`: checks one row and returns either a review or the list of problems.
  - `duplicates.py`: looks up which content hashes already exist in the project.
  - `service.py`: runs the import, stores the import record, its errors and its reviews, and writes the audit entry.
  - `router.py`: `GET /projects/{project_id}/imports`, `POST /projects/{project_id}/imports` (multipart upload), `GET /projects/{project_id}/imports/{import_id}`.
- **Frontend:** `frontend/pages/4_Reviews.py`, with the CSV upload and a manual review form.
- **Tests:** `backend/tests/test_imports.py` and `backend/tests/test_reviews.py`.

## Story B – Exact duplicate detection

### Acceptance criteria and where they are met

| Criterion | Where |
|-----------|-------|
| Same text in the same project is not saved twice | `UNIQUE (project_id, content_hash)` in the migration, checked in `service.py` through `duplicates.py` |
| Duplicates inside one file and duplicates of existing reviews are handled the same way | `test_duplicates_inside_the_file_are_skipped`, `test_review_that_already_exists_is_skipped` |
| Re-importing the same file adds nothing and reports the number of duplicates | `test_importing_the_same_file_twice_adds_nothing`; the result includes `duplicate_rows` |
| Reviews in another project are not duplicates | `test_same_reviews_can_be_imported_into_another_project` |
| Manual reviews get the same check | `test_duplicate_content_409_ignoring_case_and_spacing` in `test_reviews.py` (HTTP 409) |

### How it works

1. Each valid row gets a `content_hash`.
2. One query asks the database which of these hashes already exist in the project (in chunks of 500).
3. Rows whose hash is already known, either from the database or earlier in the same file, are counted as duplicates and not inserted.
4. The inserts run in one transaction. If another request inserts the same review at the same moment, the database constraint raises an error, the import is rolled back, and the user gets HTTP 409 with a message to try again.

### Known limits

- Only exact duplicates (after the normalization above) are detected. Similar reviews are out of scope and belong to the extended requirement FR11 (embeddings).
- `content_hash` is computed only from `content`. Two reviews with the same text but different rating or date are duplicates.

## Next steps

- The code refers to two follow-up stories: **#7** (extending the row rules in `validation.py`) and **#8** (extending duplicate detection in `duplicates.py`). Their scope is not described in the repository.
- Tests have been written but this document does not record a test run. Run `cd backend && uv run pytest --cov=app` to confirm the current state.

## Process

- Each story is reviewed in a pull request by a developer other than its author.
- The Trello card is moved to *Done* and linked to the pull request.
