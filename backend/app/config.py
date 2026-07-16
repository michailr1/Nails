from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    app_timezone: str = Field(alias="APP_TIMEZONE", min_length=1)
    database_url: str = Field(alias="DATABASE_URL", min_length=1)
    internal_api_key: SecretStr = Field(alias="INTERNAL_API_KEY", min_length=32)
    feedback_retention_days: int = Field(
        default=30,
        alias="FEEDBACK_RETENTION_DAYS",
        ge=1,
        le=365,
    )

    @field_validator("app_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("APP_TIMEZONE must not be empty")
        try:
            ZoneInfo(candidate)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("APP_TIMEZONE must be a valid IANA timezone") from exc
        return candidate

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg SQLAlchemy driver")
        return candidate

    @field_validator("internal_api_key")
    @classmethod
    def validate_internal_api_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().strip()) < 32:
            raise ValueError("INTERNAL_API_KEY must contain at least 32 characters")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
