import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_accept_valid_iana_timezone() -> None:
    settings = Settings(
        APP_TIMEZONE="Europe/Berlin",
        DATABASE_URL="postgresql+psycopg://user:pass@db:5432/nails",
    )
    assert settings.app_timezone == "Europe/Berlin"


@pytest.mark.parametrize("timezone", ["", "UTC+3", "Europe/NotARealCity"])
def test_settings_reject_invalid_timezone(timezone: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_TIMEZONE=timezone,
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/nails",
        )


def test_settings_require_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_TIMEZONE", raising=False)
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+psycopg://user:pass@db:5432/nails")


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
        Settings(APP_TIMEZONE="Europe/Berlin", DATABASE_URL=database_url)
