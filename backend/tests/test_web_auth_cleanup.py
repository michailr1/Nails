from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import get_session_factory
from app.services.web_auth_cleanup import cleanup_web_auth_state
from app.web_auth_models import (
    WebAuthRateBucket,
    WebChallengeStatus,
    WebLoginChallenge,
    WebSession,
)


def test_cleanup_removes_only_stale_web_auth_state(clean_database, create_user):
    user = create_user()
    now = datetime.now(UTC)
    stale = now - timedelta(days=10)
    active_until = now + timedelta(hours=1)

    stale_challenge_id = uuid.uuid4()
    active_challenge_id = uuid.uuid4()
    stale_session_id = uuid.uuid4()
    active_session_id = uuid.uuid4()

    with get_session_factory()() as session:
        session.add_all(
            [
                WebLoginChallenge(
                    id=stale_challenge_id,
                    verification_number_hash="a" * 64,
                    browser_token_hash="b" * 64,
                    pending_scope_hash="c" * 64,
                    status=WebChallengeStatus.expired.value,
                    attempt_count=0,
                    max_attempts=3,
                    request_ip_hash="d" * 64,
                    request_id="cleanup-stale-challenge",
                    expires_at=stale,
                ),
                WebLoginChallenge(
                    id=active_challenge_id,
                    verification_number_hash="e" * 64,
                    browser_token_hash="f" * 64,
                    pending_scope_hash="0" * 64,
                    status=WebChallengeStatus.pending.value,
                    attempt_count=0,
                    max_attempts=3,
                    request_ip_hash="1" * 64,
                    request_id="cleanup-active-challenge",
                    expires_at=active_until,
                ),
                WebSession(
                    id=stale_session_id,
                    token_hash="2" * 64,
                    user_id=user.id,
                    last_seen_at=stale,
                    idle_expires_at=stale,
                    absolute_expires_at=stale,
                    rotation_counter=1,
                    created_ip_hash="3" * 64,
                    last_ip_hash="4" * 64,
                    request_id="cleanup-stale-session",
                ),
                WebSession(
                    id=active_session_id,
                    token_hash="5" * 64,
                    user_id=user.id,
                    last_seen_at=now,
                    idle_expires_at=active_until,
                    absolute_expires_at=active_until,
                    rotation_counter=1,
                    created_ip_hash="6" * 64,
                    last_ip_hash="7" * 64,
                    request_id="cleanup-active-session",
                ),
                WebAuthRateBucket(
                    action="stale",
                    scope_hash="8" * 64,
                    window_started_at=stale,
                    count=1,
                ),
                WebAuthRateBucket(
                    action="active",
                    scope_hash="9" * 64,
                    window_started_at=now,
                    count=1,
                ),
            ]
        )
        session.commit()

        result = cleanup_web_auth_state(
            session,
            challenge_cutoff=now - timedelta(days=1),
            session_cutoff=now - timedelta(days=1),
            rate_bucket_cutoff=now - timedelta(days=1),
        )

        assert result.challenges_deleted == 1
        assert result.sessions_deleted == 1
        assert result.rate_buckets_deleted == 1
        assert session.get(WebLoginChallenge, stale_challenge_id) is None
        assert session.get(WebLoginChallenge, active_challenge_id) is not None
        assert session.get(WebSession, stale_session_id) is None
        assert session.get(WebSession, active_session_id) is not None
        buckets = session.scalars(select(WebAuthRateBucket)).all()
        assert [bucket.action for bucket in buckets] == ["active"]
