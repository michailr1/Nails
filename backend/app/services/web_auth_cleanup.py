from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.web_auth_models import (
    WebAuthRateBucket,
    WebChallengeStatus,
    WebLoginChallenge,
    WebSession,
)

_TERMINAL_CHALLENGE_STATUSES = {
    WebChallengeStatus.consumed.value,
    WebChallengeStatus.expired.value,
    WebChallengeStatus.locked.value,
    WebChallengeStatus.denied.value,
}


@dataclass(frozen=True, slots=True)
class WebAuthCleanupResult:
    challenges_deleted: int
    sessions_deleted: int
    rate_buckets_deleted: int


def cleanup_web_auth_state(
    session: Session,
    *,
    challenge_cutoff: datetime,
    session_cutoff: datetime,
    rate_bucket_cutoff: datetime,
) -> WebAuthCleanupResult:
    challenge_result = session.execute(
        delete(WebLoginChallenge).where(
            WebLoginChallenge.status.in_(_TERMINAL_CHALLENGE_STATUSES),
            WebLoginChallenge.expires_at < challenge_cutoff,
        )
    )
    session_result = session.execute(
        delete(WebSession).where(
            or_(
                WebSession.absolute_expires_at < session_cutoff,
                WebSession.idle_expires_at < session_cutoff,
                WebSession.revoked_at < session_cutoff,
            )
        )
    )
    rate_bucket_result = session.execute(
        delete(WebAuthRateBucket).where(
            WebAuthRateBucket.window_started_at < rate_bucket_cutoff,
        )
    )
    session.commit()
    return WebAuthCleanupResult(
        challenges_deleted=challenge_result.rowcount or 0,
        sessions_deleted=session_result.rowcount or 0,
        rate_buckets_deleted=rate_bucket_result.rowcount or 0,
    )
