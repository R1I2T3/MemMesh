CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    global_role   TEXT NOT NULL DEFAULT 'user',
    created_at    DATETIME NOT NULL DEFAULT (datetime('now'))
);
