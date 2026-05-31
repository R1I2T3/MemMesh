"""SQLite connection manager, migration runner, and admin seeder."""

import sqlite3
import uuid
from pathlib import Path

from config import settings


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db():
    """FastAPI dependency for database connection management."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def run_migrations() -> None:
    """Apply all SQL migration files in order."""
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    conn = get_connection()
    try:
        # Track applied migrations
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "  filename TEXT PRIMARY KEY,"
            "  applied_at DATETIME DEFAULT (datetime('now'))"
            ")"
        )
        applied = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM _migrations").fetchall()
        }

        migration_files = sorted(migrations_dir.glob("*.sql"))
        for mf in migration_files:
            if mf.name not in applied:
                sql = mf.read_text()
                with conn:
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT INTO _migrations (filename) VALUES (?)", (mf.name,)
                    )
                print(f"Applied migration: {mf.name}")

    finally:
        conn.close()


def seed_admin() -> None:
    """Create the superadmin account if it doesn't exist."""
    from auth.passwords import hash_password

    conn = get_connection()
    try:
        with conn:
            existing = conn.execute(
                "SELECT user_id FROM users WHERE email = ?", (settings.admin_email,)
            ).fetchone()

            if existing:
                print(f"Admin account already exists: {settings.admin_email}")
                return

            user_id = str(uuid.uuid4())
            password_hash = hash_password(settings.admin_password)
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, email, password_hash, global_role) "
                "VALUES (?, ?, ?, ?)",
                (user_id, settings.admin_email, password_hash, "superadmin"),
            )
            print(f"Superadmin created: {settings.admin_email}")
    except sqlite3.OperationalError as e:
        if "no such table: users" in str(e):
            raise RuntimeError(
                "Database tables do not exist. Please run migrations before seeding."
            ) from e
        raise
    finally:
        conn.close()
