-- Custom feedback categories per project (story #4). Mirrors the Categories section of docs/database/schema.sql.

SET search_path = public, extensions;

CREATE TABLE categories (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id  BIGINT       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        VARCHAR(80)  NOT NULL CHECK (btrim(name) <> ''),
    color       VARCHAR(7)   CHECK (color ~ '^#[0-9a-f]{6}$'),   -- #rrggbb, lower case
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Names are unique per project, ignoring case ("Billing" and "billing" are the same category).
CREATE UNIQUE INDEX uq_categories_project_name ON categories (project_id, lower(name));

-- RLS: enabled with no policies; only FastAPI (direct Postgres) reads app data.
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
