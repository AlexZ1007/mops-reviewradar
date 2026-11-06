-- Sprint 1: profiles, projects, project membership, audit log (stories #1, #2, #3).
-- Mirrors the [Sprint 1] sections of docs/database/schema.sql.

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA extensions;
SET search_path = public, extensions;

CREATE TYPE project_role AS ENUM ('owner', 'analyst', 'product_manager', 'viewer');

-- Profiles ------------------------------------------------------------------
CREATE TABLE profiles (
    id              UUID         PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           CITEXT       NOT NULL UNIQUE,
    full_name       VARCHAR(120) NOT NULL DEFAULT '',
    is_admin        BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
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

-- Projects and membership ---------------------------------------------------
CREATE TABLE projects (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    description     TEXT,
    created_by      UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    archived_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_projects_creator_name
    ON projects (created_by, lower(name)) WHERE archived_at IS NULL;

CREATE TABLE project_members (
    project_id      BIGINT       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id         UUID         NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role            project_role NOT NULL,
    added_by        UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);

CREATE INDEX ix_project_members_user ON project_members (user_id);

-- Audit ---------------------------------------------------------------------
CREATE TABLE audit_log (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT      REFERENCES projects(id) ON DELETE CASCADE,
    actor_id        UUID        REFERENCES profiles(id) ON DELETE SET NULL,
    action          VARCHAR(60) NOT NULL,
    target_type     VARCHAR(40),
    target_id       BIGINT,
    details         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_audit_log_project ON audit_log (project_id, created_at DESC);

-- RLS: enabled with no policies; only FastAPI (direct Postgres) reads app data.
ALTER TABLE profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects        ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log       ENABLE ROW LEVEL SECURITY;
