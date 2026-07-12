import pytest
from pydantic import ValidationError

from app.config import Settings

VALID_KEY = "test-only-internal-api-key-0000000000000000"


def test_settings_accept_valid_values() -> None:
    settings = Settings(
        APP_TIMEZONE="Europe/Berlin",
        DATABASE_URL="postgresql+psycopg://user:pass@db:5432/nails",
        INTERNAL_API_KEY=VALID_KEY,
    )
    assert settings.app_timezone == "Europe/Berlin"
    assert settings.internal_api_key.get_secret_value() == VALID_KEY


@pytest.mark.parametrize("timezone", ["", "UTC+3", "Europe/NotARealCity"])
def test_settings_reject_invalid_timezone(timezone: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_TIMEZONE=timezone,
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/nails",
            INTERNAL_API_KEY=VALID_KEY,
        )


def test_settings_require_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_TIMEZONE", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/nails",
            INTERNAL_API_KEY=VALID_KEY,
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:pass@db:5432/nails",
        "postgresql+asyncpg://user:pass@db:5432/nails",
        "sqlite:///nails.db",
    ],
)
def test_settings_reject_unsupported_database_driver(database_url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_TIMEZONE="Europe/Berlin",
            DATABASE_URL=database_url,
            INTERNAL_API_KEY=VALID_KEY,
        )


@pytest.mark.parametrize("internal_key", ["", "short", "x" * 31])
def test_settings_reject_short_internal_key(internal_key: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_TIMEZONE="Europe/Berlin",
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/nails",
            INTERNAL_API_KEY=internal_key,
        )
