from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import Settings, get_settings
from app.services.web_auth import _consume_rate_bucket, _keyed_hash


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
