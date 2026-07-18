from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import Settings, get_settings
from app.services.web_auth import _consume_rate_bucket, _keyed_hash, _user_agent_hash
from app.web_auth_models import (
    WebAuthRateBucket,
    WebChallengeStatus,
    WebLoginChallenge,
)

_LOGIN_COOKIE = "__Host-nails_login"


@dataclass(frozen=True, slots=True)
class ChallengeStatusView:
    challenge_id: uuid.UUID
    status: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def _request_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _settings() -> Settings:
    settings = get_settings()
    if not settings.web_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "web_auth_unavailable"},
        )
    return settings


def _raise_rate_limited(session: Session) -> None:
    session.commit()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "rate_limited"},
    )


def _raise_challenge_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "challenge_not_found"},
    )


def _advisory_lock_key(scope_hash: str) -> int:
    raw = int(scope_hash[:16], 16)
    return raw if raw < 2**63 else raw - 2**64


def _pending_scope(
    request: Request,
    settings: Settings,
) -> tuple[str, str, str | None]:
    request_ip_hash = _keyed_hash(
        _request_ip(request),
        purpose="ip",
        settings=settings,
    )
    user_agent_hash = _user_agent_hash(request, settings)
    fingerprint = f"{request_ip_hash}:{user_agent_hash or '-'}"
    pending_scope_hash = hashlib.sha256(fingerprint.encode()).hexdigest()
    return pending_scope_hash, request_ip_hash, user_agent_hash


def _ensure_bucket(
    session: Session,
    *,
    action: str,
    scope_hash: str,
    now: datetime,
) -> None:
    session.execute(
        pg_insert(WebAuthRateBucket)
        .values(
            action=action,
            scope_hash=scope_hash,
            window_started_at=now,
            count=0,
        )
        .on_conflict_do_nothing(
            constraint="uq_web_auth_rate_bucket_scope",
        )
    )


def ensure_start_bucket(session: Session, request: Request, now: datetime) -> None:
    settings = _settings()
    _ensure_bucket(
        session,
        action="challenge_start",
        scope_hash=_keyed_hash(
            _request_ip(request),
            purpose="ip",
            settings=settings,
        ),
        now=now,
    )


def ensure_approval_bucket(
    session: Session,
    identity: RequestIdentity,
    now: datetime,
) -> None:
    settings = _settings()
    _ensure_bucket(
        session,
        action="challenge_approve",
        scope_hash=_keyed_hash(
            str(identity.user_id),
            purpose="approve-account",
            settings=settings,
        ),
        now=now,
    )


def replace_pending_browser_challenge(session: Session, request: Request) -> str:
    settings = _settings()
    pending_scope_hash, _request_ip_hash, _user_agent_hash_value = _pending_scope(
        request,
        settings,
    )
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _advisory_lock_key(pending_scope_hash)},
    )
    challenges = session.scalars(
        select(WebLoginChallenge)
        .where(
            WebLoginChallenge.pending_scope_hash == pending_scope_hash,
            WebLoginChallenge.status == WebChallengeStatus.pending.value,
        )
        .with_for_update()
    ).all()
    for challenge in challenges:
        challenge.status = WebChallengeStatus.denied.value
    return pending_scope_hash


def enforce_status_rate_limit(
    session: Session,
    request: Request,
    challenge_id: uuid.UUID,
) -> None:
    settings = _settings()
    scope_hash = _keyed_hash(
        f"{challenge_id}:{_request_ip(request)}",
        purpose="status-scope",
        settings=settings,
    )
    _ensure_bucket(
        session,
        action="challenge_status",
        scope_hash=scope_hash,
        now=_now(),
    )
    allowed = _consume_rate_bucket(
        session,
        action="challenge_status",
        scope_hash=scope_hash,
        limit=settings.web_rate_status_limit,
        window_seconds=settings.web_rate_status_window_seconds,
        now=_now(),
    )
    if not allowed:
        _raise_rate_limited(session)
    session.commit()


def read_bound_challenge_status(
    session: Session,
    request: Request,
    challenge_id: uuid.UUID,
) -> ChallengeStatusView:
    settings = _settings()
    challenge = session.get(WebLoginChallenge, challenge_id)
    login_token = request.cookies.get(_LOGIN_COOKIE, "")
    if challenge is None or not login_token:
        _raise_challenge_not_found()
    supplied_hash = _keyed_hash(
        login_token,
        purpose="login-token",
        settings=settings,
    )
    if not hmac.compare_digest(supplied_hash, challenge.browser_token_hash):
        _raise_challenge_not_found()

    effective_status = challenge.status
    if (
        challenge.status
        in {
            WebChallengeStatus.pending.value,
            WebChallengeStatus.approved.value,
        }
        and _now() >= challenge.expires_at
    ):
        effective_status = WebChallengeStatus.expired.value
    return ChallengeStatusView(
        challenge_id=challenge.id,
        status=effective_status,
        expires_at=challenge.expires_at,
    )


def enforce_consume_rate_limit(
    session: Session,
    request: Request,
    challenge_id: uuid.UUID,
) -> None:
    settings = _settings()
    scope_hash = _keyed_hash(
        f"{challenge_id}:{_request_ip(request)}",
        purpose="consume-scope",
        settings=settings,
    )
    _ensure_bucket(
        session,
        action="challenge_consume",
        scope_hash=scope_hash,
        now=_now(),
    )
    allowed = _consume_rate_bucket(
        session,
        action="challenge_consume",
        scope_hash=scope_hash,
        limit=settings.web_rate_consume_limit,
        window_seconds=settings.web_rate_consume_window_seconds,
        now=_now(),
    )
    if not allowed:
        _raise_rate_limited(session)
    session.commit()


def enforce_approval_server_rate_limit(
    session: Session,
    identity: RequestIdentity,
) -> bool:
    settings = _settings()
    scope_hash = _keyed_hash(
        "internal-api",
        purpose="approve-server",
        settings=settings,
    )
    _ensure_bucket(
        session,
        action="challenge_approve_server",
        scope_hash=scope_hash,
        now=_now(),
    )
    allowed = _consume_rate_bucket(
        session,
        action="challenge_approve_server",
        scope_hash=scope_hash,
        limit=settings.web_rate_approve_server_limit,
        window_seconds=settings.web_rate_approve_window_seconds,
        now=_now(),
    )
    if not allowed:
        session.commit()
        return False
    session.commit()
    return True
