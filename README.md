# ReviewRadar – Documentation

| Document | Content |
|----------|---------|
| [setup-plan.md](docs/setup-plan.md) | Architecture, repo layout, environment, setup steps, Sprint task breakdown, DoD |
| [auth-and-roles.md](docs/auth-and-roles.md) | Roles, permission matrix, Supabase Auth integration, API, tests, acceptance criteria |
| [database/erd.md](docs/database/erd.md) | ER diagrams and schema decisions |
| [database/schema.sql](docs/database/schema.sql) | Supabase Postgres reference DDL (profiles, triggers, RLS) |
| [ReviewRadar - Checkpoint1.pdf](docs/ReviewRadar%20-%20Checkpoint1.pdf) | Requirements document (Checkpoint 1) |
| [requirments/](docs/requirments/) | Lab project requirements |

## Running locally

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/), [Supabase CLI](https://supabase.com/docs/guides/cli), [uv](https://docs.astral.sh/uv/).

### 1. Configure

```sh
cp .env.example .env
```

Fill `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY` and `SUPABASE_JWT_SECRET` from `supabase status -o env` (after step 2).

### 2. Start local Supabase (Postgres + Auth)

```sh
supabase start -x studio,imgproxy,vector,logflare,realtime,storage-api,edge-runtime,supavisor,postgres-meta,mailpit
supabase db reset    # applies supabase/migrations and seed.sql
```

### Database setup

The database is Supabase Postgres. The schema lives in plain SQL migrations in `supabase/migrations/` (managed by the Supabase CLI, not Alembic, because it references `auth.users` and uses triggers). `docs/database/schema.sql` is a reference DDL for the full planned schema, and `docs/database/erd.md` has the diagrams.

| Migration | Content |
|-----------|---------|
| `20261106000000_sprint1_auth_projects_roles.sql` | enums, `profiles` + signup trigger, `projects`, `project_members`, `audit_log`, RLS |
| `20261106120000_drop_platform_admin.sql` | removes the platform-admin role |
| `20261107000000_invitations_notifications.sql` | `project_invitations`, `notifications` |
| `20261109000000_categories.sql` | `categories` (per-project, unique name ignoring case, optional `#rrggbb` color) |

**Local database** (Docker): `supabase start ...` (step 2) creates it; `supabase db reset` drops it, re-applies every migration and runs `supabase/seed.sql`. Run `supabase db reset` again whenever you pull new migrations or want a clean slate. Postgres is exposed on `127.0.0.1:64322` (`postgres` / `postgres`), so you can inspect it with `psql` or any SQL client:

```sh
psql postgresql://postgres:postgres@127.0.0.1:64322/postgres
```

**Users:** there is no user seed. Create accounts by signing up in the UI (or `POST /auth/signup`); the `on_auth_user_created` trigger creates the matching `profiles` row. `supabase/seed.sql` documents a demo account (`demo@reviewradar.local` / `Demo12345`) to sign up with after a reset.

**Adding a schema change:**

```sh
supabase migration new <short_name>    # creates supabase/migrations/<timestamp>_<short_name>.sql
# edit the file, then:
supabase db reset                      # re-apply everything locally to verify
```

**Hosted (cloud) Supabase instead of Docker:** create a project (EU region), turn **Confirm email** off and set the minimum password length to 8 under Auth -> Email, then:

```sh
supabase link --project-ref <ref>
supabase db push                       # applies migrations to the cloud database
```

Point `SUPABASE_URL`, `DATABASE_URL` and the three keys in `.env` at the project (Dashboard -> Project Settings -> API / Database). Each developer needs their own local instance or a shared hosted one; a friend's `localhost` Supabase is not reachable from your machine.

### 3. Run the app

**Option A – uv (two terminals):**

```sh
cd backend  && uv run uvicorn app.main:app --reload    # API  -> http://127.0.0.1:8000
cd frontend && uv run streamlit run app.py             # UI   -> http://localhost:8501
```

**Option B – Docker Compose:**

```sh
docker compose up --build
```

The containers reach the host's Supabase via `host.docker.internal` (see `docker-compose.yml`).

### Tests

```sh
cd backend && uv run pytest --cov=app
```

### Stop

```sh
supabase stop
```

### Troubleshooting

- **Blank/black page at http://localhost:8501:** make sure the backend (`/health` on :8000) and Supabase are running, then hard-refresh (Ctrl+F5). Check the terminal running Streamlit for a traceback.
- **`supabase db reset` fails with `dial tcp 127.0.0.1:64322: i/o timeout`:** the database container was still (re)starting. Wait ~30 seconds after `supabase start` (check `docker ps` shows `supabase_db_mops` as healthy) and rerun it.
- **Sign-up returns "Authentication service is unavailable":** Docker Desktop or the local Supabase stack isn't running; start Docker, then `supabase start`.
- **Port errors on Windows:** local Supabase uses ports `643xx` because Hyper-V can reserve the default `5432x` range.
