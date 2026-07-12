import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("APP_TIMEZONE", "Europe/Berlin")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://nails_app:nails_test@127.0.0.1:55432/nails_test"
)

from app.db import clear_runtime_caches  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_runtime_caches():
    clear_runtime_caches()
    yield
    clear_runtime_caches()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
