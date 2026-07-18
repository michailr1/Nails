from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.main import app
from app.web_auth_models import WebLoginChallenge
from tests.conftest import WEB_ORIGIN_HEADERS


def test_concurrent_starts_leave_one_pending_challenge(clean_database):
    barrier = Barrier(2)

    def start_once() -> int:
        with TestClient(app, base_url="https://testserver") as client:
            barrier.wait(timeout=5)
            response = client.post(
                "/web/api/auth/challenges",
                headers=WEB_ORIGIN_HEADERS,
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: start_once(), range(2)))

    assert statuses == [201, 201]
    with get_session_factory()() as session:
        challenges = session.scalars(select(WebLoginChallenge)).all()
        assert len(challenges) == 2
        assert sum(challenge.status == "pending" for challenge in challenges) == 1
        assert sum(challenge.status == "denied" for challenge in challenges) == 1
