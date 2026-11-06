# ReviewRadar – Setup Plan

Scope of this plan: project skeleton, database, and the first Sprint focus — **authentication and project roles**.

Related Trello stories (board `MOPS`, list *To Do*):

| # | Story | SP | Priority |
|---|-------|----|----------|
| 1 | As a user, I want to log in so I can access my feedback projects securely. | 3 | MVP |
| 2 | As a user, I want to create a project so I can organize feedback for a product. | 3 | MVP |
| 3 | As a project owner, I want to manage project roles so I can control who can access and edit feedback. | 5 | Extended (FR09) |

Requirements covered: FR01, FR02, FR09, NFR01, NFR06.

## 1. Architecture

```mermaid
flowchart LR
    UI[Streamlit frontend<br/>:8501] -- "sign up / sign in" --> SA[Supabase Auth]
    UI -- "HTTP + Bearer Supabase JWT" --> API[FastAPI backend<br/>:8000]
    API -- "verify JWT (JWKS)" --> SA
    API -- SQLAlchemy --> DB[(Supabase Postgres)]
    SA --- DB
    API -. async jobs .-> HF[Hugging Face models]
```

- **Supabase** provides Postgres and Auth in one project. Accounts live in `auth.users`; app data in the `public` schema.
- Streamlit talks to Supabase **only for authentication**, then calls FastAPI with the access token. It never reads app tables.
- FastAPI verifies the Supabase JWT, enforces roles and owns all business rules.
- Schema: [database/schema.sql](database/schema.sql). Auth design: [auth-and-roles.md](auth-and-roles.md).

## 2. Repository layout

```
mops/
├── supabase/
│   ├── config.toml              # Supabase CLI local config (auth settings, ports)
│   ├── migrations/              # SQL migrations (from docs/database/schema.sql)
│   └── seed.sql                 # local test users / data
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, router registration
│   │   ├── config.py            # settings from env (pydantic-settings)
│   │   ├── db.py                # engine, SessionLocal, get_db dependency
│   │   ├── models/              # SQLAlchemy ORM models (map existing tables)
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── auth/
│   │   │   ├── jwt.py           # Supabase JWT verification (JWKS)
│   │   │   ├── dependencies.py  # get_current_user, require_permission
│   │   │   └── router.py        # /me
│   │   └── projects/
│   │       ├── router.py        # /projects, /projects/{id}/members
│   │       ├── permissions.py   # PERMISSIONS mapping
│   │       └── service.py       # business rules (last-owner rule, etc.)
│   ├── scripts/make_admin.py    # sets profiles.is_admin for ADMIN_EMAIL
│   ├── tests/                   # pytest (unit + API)
│   └── pyproject.toml
├── frontend/
│   ├── Home.py                  # sign in / sign up page
│   ├── pages/                   # Projects, Members, Import, Dashboard
│   ├── auth.py                  # supabase-py client, session handling
│   └── api_client.py            # requests wrapper adding Bearer token
├── docs/
├── .env.example
└── README.md
```

Migrations are managed with the **Supabase CLI** (plain SQL), not Alembic, because the schema references `auth.users` and uses triggers. SQLAlchemy models only map the tables.

## 3. Environment

| Tool | Purpose |
|------|---------|
| Python 3.12+ | backend + frontend |
| Supabase (cloud project) | shared dev database + auth |
| Supabase CLI + Docker | local Supabase stack for development and integration tests |
| FastAPI / Uvicorn | API |
| SQLAlchemy 2.x + psycopg 3 | DB access |
| PyJWT[crypto] | Supabase JWT verification |
| supabase-py | auth calls from Streamlit |
| Streamlit | UI |
| pytest, pytest-cov, httpx | tests + coverage |

`.env.example` (values from Supabase Dashboard → Project Settings → API / Database, or `supabase status` locally):

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres
API_BASE_URL=http://localhost:8000
ADMIN_EMAIL=admin@reviewradar.local
```

`.env` is git-ignored; only `.env.example` is committed. `SUPABASE_SECRET_KEY` and `DATABASE_URL` are used by the backend only.

## 4. Setup steps

1. **Repository** – create GitHub repo, protect `main` (PR + 1 review), `.gitignore` (Python, `.env`, `.venv`, `__pycache__`, `.coverage`, `supabase/.temp`).
2. **Supabase project** – create the cloud project (region EU). Auth → Email provider on, **Confirm email off** (accounts are auto-confirmed), minimum password length 8. Locally: `[auth.email] enable_confirmations = false` in `supabase/config.toml`. Add team members to the Supabase organization.
3. **Local Supabase** – `supabase init`, `supabase start` (runs Postgres + Auth in Docker), `supabase link --project-ref <ref>`.
4. **Schema** – first migration with enums, `profiles` + triggers, `projects`, `project_members`, `audit_log`, RLS enable. `supabase db reset` locally, `supabase db push` to cloud. Other tables come with their stories.
5. **Backend skeleton** – FastAPI app with `/health`, settings, DB session dependency.
6. **Auth** – JWKS verification, `get_current_user`, `/me`. See [auth-and-roles.md](auth-and-roles.md).
7. **Projects + roles** – project CRUD, membership endpoints, `require_permission` dependency.
8. **Admin** – sign up the admin account, run `scripts/make_admin.py`.
9. **Frontend** – sign in / sign up / sign out with `supabase-py`, session in `st.session_state`, projects list, members page.
10. **Tests + CI** – unit/API tests with dependency overrides (no Supabase needed); GitHub Actions runs `pytest --cov` on every PR. Optional integration job with `supabase start`.

Run locally:

```bash
supabase start
```

```bash
supabase db reset
```

```bash
cd backend && uvicorn app.main:app --reload
```

```bash
cd frontend && streamlit run Home.py
```

## 5. Task breakdown (Sprint focus)

| Story | Task | Approach |
|-------|------|----------|
| #1 Login | Supabase project + local CLI setup | – |
| #1 Login | Migration: `profiles` + sign-up trigger + RLS | – |
| #1 Login | Supabase JWT verification + `get_current_user` | TDD |
| #1 Login | `/me` endpoint | TDD |
| #1 Login | Streamlit sign in / sign up / sign out | Pair programming |
| #2 Project | Migration: `projects`, `project_members`, `audit_log` | – |
| #2 Project | Create / list / get / update / archive project API | TDD |
| #2 Project | Creator becomes `owner` in same transaction | TDD |
| #2 Project | Streamlit projects page | Pair programming |
| #3 Roles | `require_permission` dependency + `PERMISSIONS` map | TDD |
| #3 Roles | Member endpoints (add by email, change role, remove) | TDD |
| #3 Roles | Last-owner protection rule | TDD |
| #3 Roles | Streamlit members page (owner only) | Pair programming |

Dependencies: #1 → #2 → #3. Every later story (import, analysis, dashboard) depends on #3's permission check.

## 6. Definition of Done (for these stories)

- Acceptance criteria in [auth-and-roles.md](auth-and-roles.md#7-acceptance-criteria) pass.
- Unit + API tests written and green in CI; coverage of `app/auth` and `app/projects` ≥ 80%.
- Code reviewed via PR by a developer other than the author.
- No secrets in the repository.
- Trello card moved to *Done* and linked to the PR.
