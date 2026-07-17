from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
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

    web_auth_enabled: bool = Field(default=False, alias="WEB_AUTH_ENABLED")
    web_auth_hmac_key: SecretStr = Field(default=SecretStr(""), alias="WEB_AUTH_HMAC_KEY")
    web_allowed_hosts: str = Field(default="localhost,127.0.0.1,testserver", alias="WEB_ALLOWED_HOSTS")
    web_allowed_origins: str = Field(default="", alias="WEB_ALLOWED_ORIGINS")
    web_challenge_ttl_seconds: int = Field(
        default=600,
        alias="WEB_CHALLENGE_TTL_SECONDS",
        ge=60,
        le=1800,
    )
    web_challenge_max_attempts: int = Field(
        default=5,
        alias="WEB_CHALLENGE_MAX_ATTEMPTS",
        ge=1,
        le=10,
    )
    web_session_idle_ttl_seconds: int = Field(
        default=43200,
        alias="WEB_SESSION_IDLE_TTL_SECONDS",
        ge=300,
        le=86400,
    )
    web_session_absolute_ttl_seconds: int = Field(
        default=604800,
        alias="WEB_SESSION_ABSOLUTE_TTL_SECONDS",
        ge=3600,
        le=2592000,
    )
    web_session_touch_interval_seconds: int = Field(
        default=300,
        alias="WEB_SESSION_TOUCH_INTERVAL_SECONDS",
        ge=30,
        le=3600,
    )
    web_rate_start_limit: int = Field(default=5, alias="WEB_RATE_START_LIMIT", ge=1, le=100)
    web_rate_start_window_seconds: int = Field(
        default=900,
        alias="WEB_RATE_START_WINDOW_SECONDS",
        ge=60,
        le=86400,
    )
    web_rate_approve_limit: int = Field(default=10, alias="WEB_RATE_APPROVE_LIMIT", ge=1, le=100)
    web_rate_approve_window_seconds: int = Field(
        default=600,
        alias="WEB_RATE_APPROVE_WINDOW_SECONDS",
        ge=60,
        le=86400,
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

    @field_validator("web_allowed_hosts", "web_allowed_origins")
    @classmethod
    def normalize_csv(cls, value: str) -> str:
        return ",".join(item.strip() for item in value.split(",") if item.strip())

    @model_validator(mode="after")
    def validate_web_auth(self) -> "Settings":
        if self.web_auth_enabled and len(self.web_auth_hmac_key.get_secret_value().strip()) < 32:
            raise ValueError("WEB_AUTH_HMAC_KEY must contain at least 32 characters when web auth is enabled")
        if self.web_session_absolute_ttl_seconds < self.web_session_idle_ttl_seconds:
            raise ValueError("WEB_SESSION_ABSOLUTE_TTL_SECONDS must be at least the idle TTL")
        return self

    @property
    def allowed_web_hosts(self) -> frozenset[str]:
        return frozenset(item for item in self.web_allowed_hosts.split(",") if item)

    @property
    def allowed_web_origins(self) -> frozenset[str]:
        return frozenset(item for item in self.web_allowed_origins.split(",") if item)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
