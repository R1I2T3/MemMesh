import os
import sqlite3
import uuid
import bcrypt
from pathlib import Path
from typing import Optional


class AuthStore:
    def __init__(self, db_path: str = "data/memmesh.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._run_migrations()

    def _run_migrations(self):
        migration_path = Path(__file__).parent / "migrations" / "001_auth_sessions.sql"
        if migration_path.exists():
            sql = migration_path.read_text()
            self.conn.executescript(sql)
            self.conn.commit()

    def close(self):
        self.conn.close()

    def create_team(self, name: str) -> str:
        team_id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO teams (id, name) VALUES (?, ?)", (team_id, name))
        self.conn.commit()
        return team_id

    def get_team(self, team_id: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        return dict(row) if row else None

    def create_user(self, email: str, password: str, team_id: Optional[str] = None, is_admin: bool = False) -> str:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO users (id, email, password_hash, team_id, is_admin) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, password_hash, team_id, is_admin),
        )
        self.conn.commit()
        return user_id

    def get_user_by_email(self, email: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["is_admin"] = bool(d["is_admin"])
        return d

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def verify_password(self, user_id: str, password: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        return bcrypt.checkpw(password.encode(), user["password_hash"].encode())

    def create_api_key(self, user_id: str, label: Optional[str] = None) -> tuple[str, str]:
        raw_key = str(uuid.uuid4())
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        self.conn.execute(
            "INSERT INTO api_keys (key_hash, user_id, label) VALUES (?, ?, ?)",
            (key_hash, user_id, label),
        )
        self.conn.commit()
        return raw_key, key_hash

    def validate_api_key(self, raw_key: str) -> Optional[dict]:
        rows = self.conn.execute(
            """
            SELECT u.*, k.key_hash FROM api_keys k
            JOIN users u ON k.user_id = u.id
            WHERE k.revoked_at IS NULL
            """
        ).fetchall()
        for row in rows:
            if bcrypt.checkpw(raw_key.encode(), row["key_hash"].encode()):
                user = dict(row)
                user.pop("key_hash", None)
                user["is_admin"] = bool(user.get("is_admin", False))
                return user
        return None

    def revoke_api_key(self, key_hash: str):
        self.conn.execute(
            "UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP WHERE key_hash = ?",
            (key_hash,),
        )
        self.conn.commit()
