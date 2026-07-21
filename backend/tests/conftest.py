import os
import uuid
from collections.abc import Callable
from datetime import date, time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "i" * 64)
TEST_CLIENT_INTERNAL_API_KEY = "c" * 64
TEST_CLIENT_OWNER_TELEGRAM_USER_ID = 100000001
TEST_WEB_AUTH_HMAC_KEY = "w" * 64

os.environ.setdefault("APP_TIMEZONE", "Europe/Berlin")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://nails_app:nails_test@127.0.0.1:55432/nails_test",
)
os.environ.setdefault("INTERNAL_API_KEY", TEST_INTERNAL_API_KEY)
os.environ.setdefault("CLIENT_API_ENABLED", "true")
os.environ.setdefault("CLIENT_INTERNAL_API_KEY", TEST_CLIENT_INTERNAL_API_KEY)
os.environ.setdefault(
    "CLIENT_OWNER_TELEGRAM_USER_ID",
    str(TEST_CLIENT_OWNER_TELEGRAM_USER_ID),
)
os.environ.setdefault("WEB_AUTH_ENABLED", "true")
os.environ.setdefault("WEB_AUTH_HMAC_KEY", TEST_WEB_AUTH_HMAC_KEY)
os.environ.setdefault("WEB_ALLOWED_HOSTS", "testserver")
os.environ.setdefault("WEB_ALLOWED_ORIGINS", "https://testserver")

from app.db import clear_runtime_caches, get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AvailabilityInterval, Service, User, UserRole  # noqa: E402
from app.services.normalization import normalize_public_name  # noqa: E402

WEB_ORIGIN_HEADERS = {"Origin": "https://testserver"}


@pytest.fixture(autouse=True)
def reset_runtime_caches():
    clear_runtime_caches()
    yield
    clear_runtime_caches()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def clean_database():
    tables = (
        "web_auth_rate_buckets",
        "web_sessions",
        "web_login_challenges",
        "feedback_events",
        "audit_events",
        "onboarding_drafts",
        "onboarding_states",
        "master_preferences",
        "bookings",
        "availability_intervals",
        "client_telegram_identities",
        "clients",
        "services",
        "users",
    )
    statement = text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE")
    with get_engine().begin() as connection:
        connection.execute(statement)
    yield
    with get_engine().begin() as connection:
        connection.execute(statement)


@pytest.fixture
def create_user(clean_database) -> Callable[..., User]:
    def factory(
        telegram_user_id: int = 100000001,
        *,
        role: UserRole = UserRole.master,
        is_active: bool = True,
    ) -> User:
        with get_session_factory()() as session:
            user = User(
                id=uuid.uuid4(),
                telegram_user_id=telegram_user_id,
                role=role,
                is_active=is_active,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
            return user

    return factory


@pytest.fixture
def create_service(clean_database) -> Callable[..., Service]:
    def factory(
        owner_user_id,
        *,
        public_name: str = "Маникюр",
        price_amount: Decimal = Decimal("2500.00"),
        currency: str = "RUB",
        duration_minutes: int = 120,
        buffer_before_minutes: int = 0,
        buffer_after_minutes: int = 21,
        is_active: bool = True,
    ) -> Service:
        with get_session_factory()() as session:
            service = Service(
                owner_user_id=owner_user_id,
                public_name=public_name,
                normalized_public_name=normalize_public_name(public_name),
                public_description=None,
                price_amount=price_amount,
                currency=currency,
                duration_minutes=duration_minutes,
                buffer_before_minutes=buffer_before_minutes,
                buffer_after_minutes=buffer_after_minutes,
                is_active=is_active,
            )
            session.add(service)
            session.commit()
            session.refresh(service)
            session.expunge(service)
            return service

    return factory


@pytest.fixture
def create_availability(clean_database) -> Callable[..., AvailabilityInterval]:
    def factory(
        owner_user_id,
        *,
        day: date = date(2026, 7, 18),
        start_time: time | None = time(11, 0),
        end_time: time | None = time(20, 0),
        is_available: bool = True,
        note: str | None = None,
    ) -> AvailabilityInterval:
        with get_session_factory()() as session:
            interval = AvailabilityInterval(
                owner_user_id=owner_user_id,
                day=day,
                start_time=start_time,
                end_time=end_time,
                is_available=is_available,
                note=note,
            )
            session.add(interval)
            session.commit()
            session.refresh(interval)
            session.expunge(interval)
            return interval

    return factory


@pytest.fixture
def auth_headers() -> Callable[..., dict[str, str]]:
    def factory(
        telegram_user_id: int = 100000001,
        *,
        request_id: str = "test-request-001",
        internal_key: str = TEST_INTERNAL_API_KEY,
    ) -> dict[str, str]:
        return {
            "X-Nails-Internal-Key": internal_key,
            "X-Telegram-User-ID": str(telegram_user_id),
            "X-Request-ID": request_id,
        }

    return factory


@pytest.fixture
def client_auth_headers() -> Callable[..., dict[str, str]]:
    def factory(
        telegram_user_id: int = 200000001,
        *,
        request_id: str = "client-request-001",
        internal_key: str = TEST_CLIENT_INTERNAL_API_KEY,
    ) -> dict[str, str]:
        return {
            "X-Nails-Client-Internal-Key": internal_key,
            "X-Telegram-User-ID": str(telegram_user_id),
            "X-Request-ID": request_id,
        }

    return factory
