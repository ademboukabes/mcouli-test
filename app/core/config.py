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

    PHOTO_APPROVAL_TIMEOUT_DAYS: int = 7
    EVENT_LIFECYCLE_POLL_INTERVAL_SECONDS: int = 60
    # How long after an event's end_date approved photos stay in MinIO before
    # being cleaned up. Direct-uploaded photos additionally require a
    # confirmed Drive sync before cleanup is eligible (see
    # ListPhotosDueForStorageCleanup) — MinIO is their only copy until then.
    PHOTO_STORAGE_RETENTION_DAYS_AFTER_EVENT_END: int = 20
    DIRECT_UPLOAD_PRESIGN_EXPIRES_SECONDS: int = 1800
    DIRECT_UPLOAD_STALE_PENDING_MINUTES: int = 45
    DIRECT_UPLOAD_RECONCILE_POLL_INTERVAL_SECONDS: int = 300
    DIRECT_UPLOAD_MAX_BATCH_SIZE: int = 200
    # Dev/testing convenience: when true, a direct-upload group auto-approves
    # itself the moment every photo in it has been confirmed uploaded, instead
    # of waiting for a team lead to approve manually.
    AUTO_APPROVE: bool = True

    # Mobile auth/session defaults
    MOBILE_SESSION_LIMIT: int = 3
    MOBILE_SESSION_TTL_SECONDS: int = 180
    MOBILE_SESSION_DAYS: int = 7
    SESSION_ACTIVITY_THROTTLE_SECONDS: int = 60

    # Mobile access/refresh token lifetimes
    MOBILE_ACCESS_TOKEN_TTL_SECONDS: int = 900
    MOBILE_REFRESH_TOKEN_REUSE_GRACE_SECONDS: int = 30
    MOBILE_SESSION_ABSOLUTE_DAYS: int = 30

    # Mobile auth validation defaults
    MOBILE_AUTH_PASSWORD_MIN_LEN: int = 8
    MOBILE_AUTH_PASSWORD_MAX_LEN: int = 128
    MOBILE_AUTH_DEVICE_NAME_MAX_LEN: int = 64
    MOBILE_AUTH_DEVICE_TYPE_MAX_LEN: int = 32
    # Rate Limit Settings
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 60
    # In dev env, registration OTPs are fixed to this value and the email/NATS
    # send is skipped, so mobile devs can verify without a real inbox.
    DEV_OTP_BYPASS_CODE: str = "000000"
    TRUST_PROXY_HEADERS: bool = True
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
    FACE_EMBEDDING_PROVIDERS: str = "CUDAExecutionProvider,CPUExecutionProvider"
    FACE_EMBEDDING_CTX_ID: int = 0
    FACE_EMBEDDING_DET_WIDTH: int = 640
    FACE_EMBEDDING_DET_HEIGHT: int = 640

    # Google Drive OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    # drive.readonly alone can't write; drive.file alone can only see files
    # the app itself created, which would break browsing/importing existing
    # Drive folders. Both scopes together preserve the existing read/import
    # flow and add write access for syncing approved direct uploads back to
    # Drive. Existing staff connections keep their old readonly-only grant
    # until they disconnect and reconnect through the consent screen.
    GOOGLE_OAUTH_SCOPES: str = (
        "https://www.googleapis.com/auth/drive.readonly "
        "https://www.googleapis.com/auth/drive.file openid email profile"
    )
    # Folder ID (from the Drive URL) that approved direct-upload photos get
    # synced into. Empty means uploads land in the connected account's Drive
    # root instead of a specific folder.
    GOOGLE_CLUB_DRIVE_FOLDER_ID: str = ""

    FACE_ENCRYPTION_KEY: str
    FIREBASE_CREDENTIALS_PATH: str

    # Resend Email Configuration
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "onboarding@resend.dev"

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
