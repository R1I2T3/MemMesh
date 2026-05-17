import os
import sqlite3
from pathlib import Path
from typing import Optional


class SessionStore:
    def __init__(self, db_path: str = "data/memmesh.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self):
        migration_path = Path(__file__).parent / "migrations" / "001_auth_sessions.sql"
        if migration_path.exists():
            sql = migration_path.read_text()
            self.conn.executescript(sql)
            self.conn.commit()

    def close(self):
        self.conn.close()

    def save_message(self, session_id: str, user_id: str, team_id: Optional[str], role: str, content: str):
        self.conn.execute(
            "INSERT INTO session_messages (session_id, user_id, team_id, role, content) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, team_id, role, content),
        )
        self.conn.commit()

    def get_session_history(self, session_id: str, team_id: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM session_messages
                WHERE session_id = ? AND team_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (session_id, team_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def cleanup_expired(self, days: int = 30):
        self.conn.execute(
            "DELETE FROM session_messages WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        self.conn.commit()
