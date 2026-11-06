# ReviewRadar – Database ERD

DDL: [schema.sql](schema.sql). Supabase Postgres. `auth.users` is managed by Supabase Auth; the app owns everything in `public`.

## Sprint 1 – authentication, projects, roles

```mermaid
erDiagram
    AUTH_USERS ||--|| PROFILES : "trigger creates"
    PROFILES ||--o{ PROJECTS : "creates"
    PROFILES ||--o{ PROJECT_MEMBERS : "belongs to"
    PROJECTS ||--|{ PROJECT_MEMBERS : "has (>=1 owner)"
    PROJECTS ||--o{ AUDIT_LOG : "records"
    PROFILES ||--o{ AUDIT_LOG : "acts"

    AUTH_USERS {
        uuid id PK
        varchar email
        varchar encrypted_password
        timestamptz last_sign_in_at
    }
    PROFILES {
        uuid id PK,FK
        citext email UK
        varchar full_name
        boolean is_admin
        boolean is_active
    }
    PROJECTS {
        bigint id PK
        varchar name
        text description
        uuid created_by FK
        timestamptz archived_at
    }
    PROJECT_MEMBERS {
        bigint project_id PK,FK
        uuid user_id PK,FK
        project_role role
        uuid added_by FK
    }
    AUDIT_LOG {
        bigint id PK
        bigint project_id FK
        uuid actor_id FK
        varchar action
        jsonb details
    }
```

## Full model

```mermaid
erDiagram
    AUTH_USERS ||--|| PROFILES : ""
    PROFILES ||--o{ PROJECT_MEMBERS : ""
    PROJECTS ||--|{ PROJECT_MEMBERS : ""
    PROJECTS ||--o{ CATEGORIES : ""
    PROJECTS ||--o{ IMPORTS : ""
    PROJECTS ||--o{ REVIEWS : ""
    PROJECTS ||--o{ ANALYSIS_JOBS : ""
    PROJECTS ||--o{ REVIEW_GROUPS : ""
    PROJECTS ||--o{ ISSUES : ""
    IMPORTS ||--o{ IMPORT_ERRORS : ""
    IMPORTS ||--o{ REVIEWS : ""
    CATEGORIES |o--o{ REVIEWS : ""
    REVIEWS ||--o| REVIEW_SENTIMENTS : ""
    REVIEWS ||--o| REVIEW_EMBEDDINGS : ""
    REVIEWS ||--o{ SENTIMENT_CORRECTIONS : ""
    ANALYSIS_JOBS |o--o{ REVIEW_SENTIMENTS : ""
    ANALYSIS_JOBS |o--o{ REVIEW_EMBEDDINGS : ""
    ANALYSIS_JOBS |o--o{ REVIEW_GROUPS : ""
    REVIEW_GROUPS ||--o{ REVIEW_GROUP_MEMBERS : ""
    REVIEWS ||--o{ REVIEW_GROUP_MEMBERS : ""
    REVIEW_GROUPS |o--o{ ISSUES : ""
    ISSUES ||--o{ ISSUE_REVIEWS : ""
    REVIEWS ||--o{ ISSUE_REVIEWS : ""
    PROFILES |o--o{ ISSUES : "assignee"
```

## Key decisions

| Decision | Reason |
|----------|--------|
| Roles live on `project_members`, not on `profiles` | A user can be owner in one project and viewer in another (FR09). |
| Supabase Auth owns accounts (`auth.users`) | Passwords, reset and sessions are not implemented by the team. |
| `profiles` 1:1 with `auth.users`, filled by trigger | App tables reference `profiles(id)` (UUID); email copied for member lookup. |
| `profiles.is_admin` is the only global role | Platform admin manages users and can recover projects with no owner. |
| RLS enabled on all `public` tables, no policies | The public anon key cannot read app data through the Supabase Data API; FastAPI is the only reader. |
| `UNIQUE (project_id, content_hash)` on `reviews` | Exact duplicates rejected at DB level, re-importing a file is idempotent (FR04, NFR04). |
| `imports.file_sha256` | Warn the user when the same file is uploaded again. |
| `review_sentiments.predicted_label` + `final_label` | Keeps the AI estimate and the human correction separately (NFR05). |
| `projects.archived_at` soft delete | Project data is kept for audit; archived projects are hidden. |
| `audit_log` | Role changes and project actions are traceable (story #3, FR15). |
| Tables added per story | Sprint 1 migration contains only `profiles`, `projects`, `project_members`, `audit_log`. |
