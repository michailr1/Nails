from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

from sqlalchemy import select

from app.db import get_session_factory
from app.services.web_auth import _consume_rate_bucket
from app.services.web_auth_rate_bucket import _ensure_bucket
from app.web_auth_models import WebAuthRateBucket


def test_first_rate_bucket_insert_is_concurrency_safe(clean_database):
    barrier = Barrier(2)
    now = datetime.now(UTC)

    def consume_once() -> bool:
        with get_session_factory()() as session:
            barrier.wait(timeout=5)
            _ensure_bucket(
                session,
                action="concurrent_test",
                scope_hash="same-scope",
                now=now,
            )
            allowed = _consume_rate_bucket(
                session,
                action="concurrent_test",
                scope_hash="same-scope",
                limit=10,
                window_seconds=600,
                now=now,
            )
            session.commit()
            return allowed

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: consume_once(), range(2)))

    assert results == [True, True]
    with get_session_factory()() as session:
        buckets = session.scalars(
            select(WebAuthRateBucket).where(
                WebAuthRateBucket.action == "concurrent_test",
                WebAuthRateBucket.scope_hash == "same-scope",
            )
        ).all()
        assert len(buckets) == 1
        assert buckets[0].count == 2
