from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str = "multAI"
    environment: str = "dev"
    debug: bool = True
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]

    # Redis
    REDIS_PORT: int
    REDIS_HOST: str
    REDIS_PASSWORD: str = ""

    # nats
    NATS_PORT: int
    NATS_HOST: str
    NATS_PASSWORD: str
    NATS_USER: str
    # MinIO
    MINIO_API_PORT: int
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_HOST: str
    MINIO_RETRY_ATTEMPTS: int = 3
    MINIO_RETRY_BASE_SECONDS: float = 0.5

    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Mobile auth/session defaults
    MOBILE_SESSION_LIMIT: int = 3
    MOBILE_SESSION_TTL_SECONDS: int = 180
    MOBILE_SESSION_DAYS: int = 7
    # Admin list defaults
    ADMIN_USERS_DEFAULT_LIMIT: int = 20
    ADMIN_USERS_MAX_LIMIT: int = 100
    # Security
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    encryption_key: str
    totp_issuer: str = "multAI"

    # Face embedding model
    FACE_EMBEDDING_MODEL_NAME: str = "buffalo_l"
    FACE_EMBEDDING_PROVIDERS: str = "CPUExecutionProvider"
    FACE_EMBEDDING_CTX_ID: int = -1
    FACE_EMBEDDING_DET_WIDTH: int = 640
    FACE_EMBEDDING_DET_HEIGHT: int = 640

    # Google Drive OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    GOOGLE_OAUTH_SCOPES: str = (
        "https://www.googleapis.com/auth/drive.readonly openid email profile"
    )

    FACE_ENCRYPTION_KEY: str
    FIREBASE_CREDENTIALS_PATH: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return True
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"release", "prod", "production", "false", "0", "no"}:
                return False
            if lowered in {"true", "1", "yes"}:
                return True
            return value
        return value


settings = Settings()  # type: ignore
