from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://shuvit:shuvit@localhost:5432/shuvit"
    REDIS_URL: str = "redis://localhost:6379/0"
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "Shuvit <noreply@shuvit.app>"
    JWT_SECRET: str = "change-me-to-a-64-char-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 7 * 24 * 60
    BASE_URL: str = "https://api.shuvit.app"
    MEDIA_DIR: str = "./media_uploads"
    ADMIN_EMAILS: str = ""
    CORS_ORIGINS: str = "https://shuvit.app,https://www.shuvit.app"
    MAX_IMAGE_SIZE: int = 20 * 1024 * 1024
    MAX_VIDEO_SIZE: int = 50 * 1024 * 1024
    ALLOW_VIDEO_UPLOADS: bool = False
    MAGIC_LINK_EXPIRE_MINUTES: int = 15
    MAGIC_LINK_RATE_LIMIT_SECONDS: int = 60

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

if settings.JWT_SECRET == "change-me-to-a-64-char-random-string":
    import warnings
    warnings.warn(
        "JWT_SECRET is using the default placeholder. Set a real secret in .env!",
        stacklevel=1,
    )
