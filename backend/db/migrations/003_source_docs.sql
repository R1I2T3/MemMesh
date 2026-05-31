-- backend/db/migrations/003_source_docs.sql
CREATE TABLE source_docs (
    doc_id        TEXT PRIMARY KEY,
    team_id       TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    -- file_type stores MIME type (e.g. application/pdf, text/plain)
    file_type     TEXT NOT NULL,
    file_size     INTEGER NOT NULL,
    content_hash  TEXT NOT NULL,
    storage_path  TEXT NOT NULL UNIQUE,
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'indexing', 'indexed', 'failed')),
    error_message TEXT,
    uploaded_by   TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at    DATETIME NOT NULL DEFAULT (datetime('now')),
    UNIQUE(team_id, content_hash)
);

CREATE INDEX idx_source_docs_team_id ON source_docs(team_id);
CREATE INDEX idx_source_docs_team_status ON source_docs(team_id, status);
