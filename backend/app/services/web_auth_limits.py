from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import Settings, get_settings
from app.services.web_auth import _consume_rate_bucket, _keyed_hash
from app.web_auth_models import WebChallengeStatus, WebLoginChallenge

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


def invalidate_pending_browser_challenge(session: Session, request: Request) -> None:
    login_token = request.cookies.get(_LOGIN_COOKIE, "")
    if not login_token:
        return
    settings = _settings()
    browser_token_hash = _keyed_hash(
        login_token,
        purpose="login-token",
        settings=settings,
    )
    challenge = session.scalar(
        select(WebLoginChallenge)
        .where(
            WebLoginChallenge.browser_token_hash == browser_token_hash,
            WebLoginChallenge.status == WebChallengeStatus.pending.value,
        )
        .with_for_update()
    )
    if challenge is None:
        return
    challenge.status = WebChallengeStatus.denied.value
    session.commit()


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
