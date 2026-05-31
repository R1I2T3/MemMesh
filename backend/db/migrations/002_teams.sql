-- backend/db/migrations/002_teams.sql
CREATE TABLE teams (
    team_id     TEXT PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE team_members (
    membership_id TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    team_id       TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'lead')),
    added_by      TEXT REFERENCES users(user_id) ON DELETE SET NULL,
    added_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, team_id)
);

CREATE INDEX idx_team_members_team_id ON team_members(team_id);
CREATE INDEX idx_team_members_added_by ON team_members(added_by);

