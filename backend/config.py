from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "app_user"
    MYSQL_PASSWORD: str = "user_password_change_me"
    MYSQL_DATABASE: str = "memmesh"

    WEAVIATE_HOST: str = "127.0.0.1"
    WEAVIATE_PORT: int = 8080
    WEAVIATE_GRPC_PORT: int = 50051

    NEO4J_URI: str = "bolt://127.0.0.1:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j_password_change_me"

    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    PHOENIX_COLLECTOR_ENDPOINT: str = "http://127.0.0.1:6006"

    SUPERADMIN_EMAIL: str = "superadmin@memmesh.com"
    SUPERADMIN_PASSWORD: str = "admin_secret_password_change_me"

    JWT_SECRET: str = "super_secret_jwt_key_change_me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    MAX_UPLOAD_SIZE_MB: int = 50

    SEMANTIC_CACHE_TTL: int = 86400  # 24 hours
    SEMANTIC_CACHE_THRESHOLD: float = 0.92

    RATE_LIMIT_LOGIN: str = "30/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"
    RATE_LIMIT_QUERY: str = "30/minute"
    RATE_LIMIT_GLOBAL: str = "100/minute"

    model_config = SettingsConfigDict(env_file=[".env", "../.env"], env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

settings = Settings()
