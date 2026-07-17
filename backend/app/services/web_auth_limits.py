from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import Settings, get_settings
from app.services.web_auth import _consume_rate_bucket, _keyed_hash
from app.web_auth_models import WebLoginChallenge

_LOGIN_COOKIE = "__Host-nails_login"


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


def enforce_status_browser_binding(
    session: Session,
    request: Request,
    challenge_id: uuid.UUID,
) -> None:
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
