from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "multAI"
    environment: str = "dev"
    debug: bool = True

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

    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Security
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    encryption_key: str
    totp_issuer: str = "multAI"

    # Google Drive OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    GOOGLE_OAUTH_SCOPES: str = (
        "https://www.googleapis.com/auth/drive.readonly openid email profile"
    )

    FACE_ENCRYPTION_KEY: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()  # type: ignore
