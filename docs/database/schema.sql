-- ReviewRadar – Supabase (PostgreSQL) schema, reference DDL for the public schema
-- Source of truth for the SQLAlchemy models and Alembic migrations.
-- Sections marked [Sprint 1] are needed for authentication, projects and roles.

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA extensions;   -- case-insensitive email
SET search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------
CREATE TYPE project_role     AS ENUM ('owner', 'analyst', 'product_manager', 'viewer');
CREATE TYPE review_source    AS ENUM ('csv', 'manual');
CREATE TYPE import_status    AS ENUM ('pending', 'processing', 'completed', 'failed');
CREATE TYPE job_status       AS ENUM ('queued', 'running', 'completed', 'failed');
CREATE TYPE job_type         AS ENUM ('sentiment', 'embedding', 'grouping');
CREATE TYPE sentiment_label  AS ENUM ('positive', 'neutral', 'negative');
CREATE TYPE issue_status     AS ENUM ('open', 'in_progress', 'resolved', 'closed');

-- ---------------------------------------------------------------------------
-- [Sprint 1] Profiles (FR01)
-- Accounts, passwords and sessions are owned by Supabase Auth (auth.users).
-- profiles holds app data for each auth user; created by trigger on sign-up.
-- ---------------------------------------------------------------------------
CREATE TABLE profiles (
    id              UUID         PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           CITEXT       NOT NULL UNIQUE,    -- copy of auth.users.email, used to invite members
    full_name       VARCHAR(120) NOT NULL DEFAULT '',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,   -- app-level block, checked by the API
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE FUNCTION public.handle_new_user() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (NEW.id, NEW.email, coalesce(NEW.raw_user_meta_data ->> 'full_name', ''));
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE FUNCTION public.handle_user_email_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
    UPDATE public.profiles SET email = NEW.email, updated_at = now() WHERE id = NEW.id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_email_changed
    AFTER UPDATE OF email ON auth.users
    FOR EACH ROW WHEN (OLD.email IS DISTINCT FROM NEW.email)
    EXECUTE FUNCTION public.handle_user_email_change();

-- ---------------------------------------------------------------------------
-- [Sprint 1] Projects and membership (FR02, FR09)
-- ---------------------------------------------------------------------------
CREATE TABLE projects (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    description     TEXT,
    created_by      UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    archived_at     TIMESTAMPTZ,                     -- soft delete
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Project names are unique per creator among active projects.
CREATE UNIQUE INDEX uq_projects_creator_name
    ON projects (created_by, lower(name)) WHERE archived_at IS NULL;

CREATE TABLE project_members (
    project_id      BIGINT       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id         UUID         NOT NULL REFERENCES profiles(id)    ON DELETE CASCADE,
    role            project_role NOT NULL,
    added_by        UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);

CREATE INDEX ix_project_members_user ON project_members (user_id);

-- ---------------------------------------------------------------------------
-- [Invitations] Project invitations and notifications (FR09, docs/invite-system.md)
-- ---------------------------------------------------------------------------
CREATE TYPE invitation_status AS ENUM ('pending', 'accepted', 'declined', 'revoked', 'expired');

CREATE TABLE project_invitations (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id    BIGINT            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    email         CITEXT            NOT NULL,
    role          project_role      NOT NULL,
    status        invitation_status NOT NULL DEFAULT 'pending',
    invited_by    UUID              REFERENCES profiles(id) ON DELETE SET NULL,
    responded_by  UUID              REFERENCES profiles(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ       NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ       NOT NULL DEFAULT now() + interval '7 days',
    responded_at  TIMESTAMPTZ
);

-- One pending invitation per project + email.
CREATE UNIQUE INDEX uq_invitations_pending
    ON project_invitations (project_id, email) WHERE status = 'pending';
CREATE INDEX ix_invitations_email ON project_invitations (email) WHERE status = 'pending';

CREATE TABLE notifications (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       UUID         NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    type          VARCHAR(40)  NOT NULL,
    project_id    BIGINT       REFERENCES projects(id) ON DELETE CASCADE,
    invitation_id BIGINT       REFERENCES project_invitations(id) ON DELETE CASCADE,
    actor_id      UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    payload       JSONB,
    read_at       TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_notifications_user ON notifications (user_id, created_at DESC);
CREATE INDEX ix_notifications_unread ON notifications (user_id) WHERE read_at IS NULL;

-- When a profile is created or its email changes, deliver pending invitations for that email.
CREATE FUNCTION public.deliver_pending_invitations() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
    INSERT INTO public.notifications (user_id, type, project_id, invitation_id, actor_id, payload)
    SELECT NEW.id, 'invitation', i.project_id, i.id, i.invited_by,
           jsonb_build_object(
               'project_name', p.name,
               'role', i.role,
               'actor_name', coalesce(nullif(a.full_name, ''), a.email::text, '')
           )
    FROM public.project_invitations i
    JOIN public.projects p ON p.id = i.project_id
    LEFT JOIN public.profiles a ON a.id = i.invited_by
    WHERE i.email = NEW.email
      AND i.status = 'pending'
      AND i.expires_at > now()
      AND p.archived_at IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM public.notifications n
          WHERE n.user_id = NEW.id AND n.invitation_id = i.id AND n.type = 'invitation'
      );
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_profile_created_deliver_invitations
    AFTER INSERT ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.deliver_pending_invitations();

CREATE TRIGGER on_profile_email_changed_deliver_invitations
    AFTER UPDATE OF email ON public.profiles
    FOR EACH ROW WHEN (OLD.email IS DISTINCT FROM NEW.email)
    EXECUTE FUNCTION public.deliver_pending_invitations();

-- ---------------------------------------------------------------------------
-- Categories (story #4)
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            VARCHAR(80)  NOT NULL,
    color           VARCHAR(7),                      -- #RRGGBB
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (project_id, name)
);

-- ---------------------------------------------------------------------------
-- Imports and reviews (FR03, FR04, FR05, FR10)
-- ---------------------------------------------------------------------------
CREATE TABLE imports (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    uploaded_by     UUID          REFERENCES profiles(id) ON DELETE SET NULL,
    file_name       VARCHAR(255)  NOT NULL,
    file_sha256     CHAR(64)      NOT NULL,          -- same file twice -> detected (NFR04)
    status          import_status NOT NULL DEFAULT 'pending',
    total_rows      INT           NOT NULL DEFAULT 0,
    imported_rows   INT           NOT NULL DEFAULT 0,
    duplicate_rows  INT           NOT NULL DEFAULT 0,
    invalid_rows    INT           NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX ix_imports_project ON imports (project_id);

CREATE TABLE import_errors (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_id       BIGINT       NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    row_number      INT          NOT NULL,
    field           VARCHAR(80),
    message         TEXT         NOT NULL
);

CREATE TABLE reviews (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    import_id       BIGINT        REFERENCES imports(id)    ON DELETE SET NULL,
    category_id     BIGINT        REFERENCES categories(id) ON DELETE SET NULL,
    created_by      UUID          REFERENCES profiles(id)      ON DELETE SET NULL,
    source          review_source NOT NULL,
    external_id     VARCHAR(120),
    author          VARCHAR(120),
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    content         TEXT          NOT NULL CHECK (length(trim(content)) > 0),
    content_hash    CHAR(64)      NOT NULL,          -- sha256 of normalized content
    reviewed_at     TIMESTAMPTZ,                     -- date of the original review
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (project_id, content_hash)                -- exact duplicate detection (FR04)
);

CREATE INDEX ix_reviews_project_date ON reviews (project_id, reviewed_at);
CREATE INDEX ix_reviews_content_fts  ON reviews USING gin (to_tsvector('simple', content));

-- ---------------------------------------------------------------------------
-- AI analysis (FR06, FR07, FR11, FR12)
-- ---------------------------------------------------------------------------
CREATE TABLE analysis_jobs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    started_by      UUID        REFERENCES profiles(id) ON DELETE SET NULL,
    type            job_type    NOT NULL,
    status          job_status  NOT NULL DEFAULT 'queued',
    model_name      VARCHAR(200) NOT NULL,
    total_items     INT         NOT NULL DEFAULT 0,
    processed_items INT         NOT NULL DEFAULT 0,
    failed_items    INT         NOT NULL DEFAULT 0,
    error_message   TEXT,
    retry_of        BIGINT      REFERENCES analysis_jobs(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);

CREATE INDEX ix_analysis_jobs_project ON analysis_jobs (project_id, created_at DESC);

-- One current sentiment per review; corrections overwrite and are logged.
CREATE TABLE review_sentiments (
    review_id       BIGINT          PRIMARY KEY REFERENCES reviews(id) ON DELETE CASCADE,
    job_id          BIGINT          REFERENCES analysis_jobs(id) ON DELETE SET NULL,
    predicted_label sentiment_label NOT NULL,
    confidence      REAL            NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    final_label     sentiment_label NOT NULL,        -- = predicted unless corrected (NFR05)
    is_corrected    BOOLEAN         NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Embeddings stored as float arrays; switch to pgvector if similarity search is done in SQL.
CREATE TABLE review_embeddings (
    review_id       BIGINT       PRIMARY KEY REFERENCES reviews(id) ON DELETE CASCADE,
    job_id          BIGINT       REFERENCES analysis_jobs(id) ON DELETE SET NULL,
    model_name      VARCHAR(200) NOT NULL,
    vector          REAL[]       NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE review_groups (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id          BIGINT       REFERENCES analysis_jobs(id) ON DELETE SET NULL,
    label           VARCHAR(200),
    size            INT          NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE review_group_members (
    group_id        BIGINT NOT NULL REFERENCES review_groups(id) ON DELETE CASCADE,
    review_id       BIGINT NOT NULL REFERENCES reviews(id)       ON DELETE CASCADE,
    similarity      REAL,
    PRIMARY KEY (group_id, review_id)
);

-- ---------------------------------------------------------------------------
-- Issues (FR13, FR14)
-- ---------------------------------------------------------------------------
CREATE TABLE issues (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    group_id        BIGINT       REFERENCES review_groups(id) ON DELETE SET NULL,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    status          issue_status NOT NULL DEFAULT 'open',
    assignee_id     UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    created_by      UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_issues_project_status ON issues (project_id, status);

CREATE TABLE issue_reviews (
    issue_id        BIGINT NOT NULL REFERENCES issues(id)  ON DELETE CASCADE,
    review_id       BIGINT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    PRIMARY KEY (issue_id, review_id)
);

-- ---------------------------------------------------------------------------
-- Audit (FR15, story #3 role changes)
-- ---------------------------------------------------------------------------
CREATE TABLE sentiment_corrections (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    review_id       BIGINT          NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    corrected_by    UUID            REFERENCES profiles(id) ON DELETE SET NULL,
    old_label       sentiment_label NOT NULL,
    new_label       sentiment_label NOT NULL,
    reason          TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT      REFERENCES projects(id) ON DELETE CASCADE,
    actor_id        UUID        REFERENCES profiles(id)    ON DELETE SET NULL,
    action          VARCHAR(60) NOT NULL,   -- e.g. member.added, member.role_changed, project.archived
    target_type     VARCHAR(40),
    target_id       BIGINT,
    details         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_audit_log_project ON audit_log (project_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- All access goes through FastAPI (direct Postgres connection), which enforces roles.
-- RLS is enabled with no policies so the public Supabase Data API (anon /
-- authenticated keys) cannot read or write these tables directly.
-- ---------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    END LOOP;
END $$;
