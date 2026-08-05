from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Neon/Render often give postgres://; SQLAlchemy+psycopg3 needs postgresql+psycopg://."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url.split("://", 1)[0]:
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LETTER_", extra="ignore")

    app_name: str = "LETTER Platform API"
    env: str = "development"
    database_url: str = "sqlite:///./letter.db"
    secret_key: str = "development-only-secret-key-change-me"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    # NoDecode: allow comma-separated origins on Render without JSON quoting issues.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    financial_transactions_enabled: bool = False
    storage_path: str = "./storage"
    storage_backend: str = "LOCAL"
    s3_bucket: str | None = None
    s3_region: str = "sa-east-1"
    s3_endpoint_url: str | None = None
    max_upload_mb: int = 10
    log_level: str = "INFO"
    worker_poll_seconds: int = 5
    worker_batch_size: int = 20
    public_rate_limit_per_minute: int = 300
    login_rate_limit_per_minute: int = 20
    integration_circuit_failure_threshold: int = 3
    integration_circuit_cooldown_seconds: int = 60
    integration_http_timeout_seconds: float = 10.0

    @field_validator("database_url", mode="before")
    @classmethod
    def parse_database_url(cls, value):
        if isinstance(value, str):
            return normalize_database_url(value.strip())
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                import json

                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    def production_issues(self) -> list[str]:
        issues=[]
        if self.env in {"staging","production"}:
            if self.database_url.startswith("sqlite"): issues.append("DATABASE_MUST_BE_POSTGRESQL")
            if self.secret_key=="development-only-secret-key-change-me" or len(self.secret_key)<32: issues.append("SECRET_KEY_WEAK")
            if self.storage_backend=="S3" and not self.s3_bucket: issues.append("S3_BUCKET_MISSING")
            if "http://localhost:3000" in self.cors_origins: issues.append("CORS_LOCALHOST_ENABLED")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
