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
    upload_dir: str

    # Knowledge Base Indexing & Embeddings
    chroma_dir: str
    falkordb_dir: str
    embedding_model: str
    gemini_api_key: str


def load_settings() -> Settings:
    """Load settings from environment variables. Raises ValueError on invalid types."""
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

    admin_password = os.getenv("ADMIN_PASSWORD", "changeme")
    if admin_password == "changeme":
        import warnings

        warnings.warn(
            "ADMIN_PASSWORD is set to the default value 'changeme'. "
            "Set a secure password in .env for production.",
            stacklevel=2,
        )

    try:
        jwt_expiry_minutes = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
    except ValueError as e:
        raise ValueError("JWT_EXPIRY_MINUTES must be a valid integer.") from e

    try:
        api_port = int(os.getenv("API_PORT", "8081"))
    except ValueError as e:
        raise ValueError("API_PORT must be a valid integer.") from e

    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key:
        import warnings
        warnings.warn(
            "GEMINI_API_KEY is not set. Ingestion of documents will fail "
            "when calling the Gemini API to generate embeddings.",
            UserWarning,
            stacklevel=2,
        )

    # Normalize data directories relative to backend root if they are relative
    backend_dir = Path(__file__).resolve().parent

    def _normalize_path(path_str: str) -> str:
        p = Path(path_str)
        if not p.is_absolute():
            p = (backend_dir / p).resolve()
        return str(p)

    return Settings(
        admin_email=os.getenv("ADMIN_EMAIL", "admin@example.com"),
        admin_password=admin_password,
        jwt_secret=jwt_secret,
        jwt_expiry_minutes=jwt_expiry_minutes,
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=api_port,
        data_dir=_normalize_path(os.getenv("DATA_DIR", "./data")),
        sqlite_path=_normalize_path(os.getenv("SQLITE_PATH", "./data/db.sqlite3")),
        upload_dir=_normalize_path(os.getenv("UPLOAD_DIR", "./data/uploads")),
        chroma_dir=_normalize_path(os.getenv("CHROMA_DIR", "./data/chroma")),
        falkordb_dir=_normalize_path(os.getenv("FALKORDB_DIR", "./data/falkordb")),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-004"),
        gemini_api_key=gemini_api_key,
    )


settings = load_settings()
