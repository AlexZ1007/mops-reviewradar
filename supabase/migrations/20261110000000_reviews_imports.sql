-- Reviews and CSV imports (stories #6 and #9).
-- Mirrors the "Imports and reviews" section of docs/database/schema.sql.

SET search_path = public, extensions;

CREATE TYPE review_source AS ENUM ('csv', 'manual');
CREATE TYPE import_status AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE imports (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    uploaded_by     UUID          REFERENCES profiles(id) ON DELETE SET NULL,
    file_name       VARCHAR(255)  NOT NULL,
    file_sha256     CHAR(64)      NOT NULL,
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

CREATE INDEX ix_import_errors_import ON import_errors (import_id);

CREATE TABLE reviews (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id      BIGINT        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    import_id       BIGINT        REFERENCES imports(id)    ON DELETE SET NULL,
    category_id     BIGINT        REFERENCES categories(id) ON DELETE SET NULL,
    created_by      UUID          REFERENCES profiles(id)   ON DELETE SET NULL,
    source          review_source NOT NULL,
    external_id     VARCHAR(120),
    author          VARCHAR(120),
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    content         TEXT          NOT NULL CHECK (length(trim(content)) > 0),
    content_hash    CHAR(64)      NOT NULL,          -- sha256 of normalized content
    reviewed_at     TIMESTAMPTZ,                     -- date of the original review
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (project_id, content_hash)                -- exact duplicate detection
);

CREATE INDEX ix_reviews_project_date ON reviews (project_id, reviewed_at);
CREATE INDEX ix_reviews_content_fts  ON reviews USING gin (to_tsvector('simple', content));

-- RLS: enabled with no policies; only FastAPI (direct Postgres) reads app data.
ALTER TABLE imports       ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_errors ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews       ENABLE ROW LEVEL SECURITY;
