import os
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("APP_TIMEZONE", "Europe/Berlin")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://nails_app:nails_test@127.0.0.1:55432/nails_test"
)
os.environ.setdefault(
    "INTERNAL_API_KEY", "test-only-internal-api-key-0000000000000000"
)

from app.db import clear_runtime_caches, get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402

TEST_INTERNAL_API_KEY = "test-only-internal-api-key-0000000000000000"


@pytest.fixture(autouse=True)
def reset_runtime_caches():
    clear_runtime_caches()
    yield
    clear_runtime_caches()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def clean_database():
    tables = (
        "audit_events",
        "onboarding_drafts",
        "onboarding_states",
        "bookings",
        "schedule_exceptions",
        "schedule_rules",
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
