from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
