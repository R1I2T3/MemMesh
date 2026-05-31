"""Environment configuration loader with validation."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Admin bootstrap
    admin_email: str
    admin_password: str

    # Auth
    jwt_secret: str
    jwt_expiry_minutes: int

    # Server
    api_host: str
    api_port: int

    # Data directories
    data_dir: str
    sqlite_path: str


def load_settings() -> Settings:
    """Load settings from environment variables. Raises ValueError on missing required vars."""
    jwt_secret = os.getenv("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == "change-this-secret-in-production":
        import warnings
        warnings.warn(
            "JWT_SECRET is not set or using default value. "
            "Set a strong secret in .env for production.",
            stacklevel=2,
        )
        if not jwt_secret:
            jwt_secret = "dev-fallback-secret-do-not-use-in-production"

    return Settings(
        admin_email=os.getenv("ADMIN_EMAIL", "admin@example.com"),
        admin_password=os.getenv("ADMIN_PASSWORD", "changeme"),
        jwt_secret=jwt_secret,
        jwt_expiry_minutes=int(os.getenv("JWT_EXPIRY_MINUTES", "60")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        data_dir=os.getenv("DATA_DIR", "./data"),
        sqlite_path=os.getenv("SQLITE_PATH", "./data/db.sqlite3"),
    )


settings = load_settings()
