from __future__ import annotations

import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import User, UserRole
from app.services.web_auth import (
    _LOGIN_COOKIE,
    _SESSION_COOKIE,
    ConsumedChallenge,
    _audit,
    _consume_rate_bucket,
    _keyed_hash,
    _now,
    _raise_rate_limited,
    _request_id,
    _request_ip,
    _settings,
    _unauthorized,
    _user_agent_hash,
    validate_web_boundary,
)
from app.web_auth_models import WebChallengeStatus, WebLoginChallenge, WebSession

PORTAL_ROLES = frozenset({UserRole.master, UserRole.admin})


@dataclass(frozen=True, slots=True)
class PortalSessionContext:
    identity: RequestIdentity
    web_session: WebSession


def consume_portal_challenge(
    session: Session,
    request: Request,
    challenge_id: uuid.UUID,
) -> ConsumedChallenge:
    validate_web_boundary(request)
    settings = _settings()
    now = _now()
    request_id = _request_id()
    rate_scope = _keyed_hash(
        f"{challenge_id}:{_request_ip(request)}",
        purpose="consume-scope",
        settings=settings,
    )
    if not _consume_rate_bucket(
        session,
        action="challenge_consume",
        scope_hash=rate_scope,
        limit=settings.web_rate_consume_limit,
        window_seconds=settings.web_rate_consume_window_seconds,
        now=now,
    ):
        _raise_rate_limited(session)

    challenge = session.scalar(
        select(WebLoginChallenge)
        .where(WebLoginChallenge.id == challenge_id)
        .with_for_update()
    )
    if challenge is None:
        session.commit()
        return ConsumedChallenge(False, "invalid")

    open_statuses = {
        WebChallengeStatus.pending.value,
        WebChallengeStatus.approved.value,
    }
    if now >= challenge.expires_at and challenge.status in open_statuses:
        challenge.status = WebChallengeStatus.expired.value
    if (
        challenge.status != WebChallengeStatus.approved.value
        or challenge.user_id is None
    ):
        session.commit()
        return ConsumedChallenge(False, challenge.status)

    login_token = request.cookies.get(_LOGIN_COOKIE, "")
    supplied_hash = ""
    if login_token:
        supplied_hash = _keyed_hash(
            login_token,
            purpose="login-token",
            settings=settings,
        )
    if not supplied_hash or not hmac.compare_digest(
        supplied_hash,
        challenge.browser_token_hash,
    ):
        challenge.attempt_count += 1
        if challenge.attempt_count >= challenge.max_attempts:
            challenge.status = WebChallengeStatus.locked.value
        session.commit()
        return ConsumedChallenge(False, challenge.status)

    user = session.scalar(
        select(User).where(
            User.id == challenge.user_id,
            User.is_active.is_(True),
            User.role.in_(PORTAL_ROLES),
        )
    )
    if user is None:
        challenge.status = WebChallengeStatus.denied.value
        session.commit()
        return ConsumedChallenge(False, challenge.status)

    session_token = secrets.token_urlsafe(32)
    request_ip_hash = _keyed_hash(
        _request_ip(request),
        purpose="ip",
        settings=settings,
    )
    web_session = WebSession(
        token_hash=_keyed_hash(
            session_token,
            purpose="session-token",
            settings=settings,
        ),
        user_id=user.id,
        target_owner_user_id=None,
        last_seen_at=now,
        idle_expires_at=now
        + timedelta(seconds=settings.web_session_idle_ttl_seconds),
        absolute_expires_at=now
        + timedelta(seconds=settings.web_session_absolute_ttl_seconds),
        rotation_counter=1,
        created_ip_hash=request_ip_hash,
        last_ip_hash=request_ip_hash,
        user_agent_hash=_user_agent_hash(request, settings),
        request_id=request_id,
    )
    session.add(web_session)
    challenge.status = WebChallengeStatus.consumed.value
    challenge.consumed_at = now
    _audit(
        session,
        action="web_session_created",
        request_id=request_id,
        object_type="web_session",
        owner_user_id=user.id,
        actor_user_id=user.id,
        object_id=web_session.id,
    )
    session.commit()
    return ConsumedChallenge(
        True,
        WebChallengeStatus.consumed.value,
        session_token,
    )


def require_portal_session_context(
    session: Session,
    request: Request,
) -> PortalSessionContext:
    validate_web_boundary(request)
    settings = _settings()
    token = request.cookies.get(_SESSION_COOKIE, "")
    if not token:
        raise _unauthorized()

    token_hash = _keyed_hash(
        token,
        purpose="session-token",
        settings=settings,
    )
    web_session = session.scalar(
        select(WebSession)
        .where(WebSession.token_hash == token_hash)
        .with_for_update()
    )
    now = _now()
    if (
        web_session is None
        or web_session.revoked_at is not None
        or now >= web_session.idle_expires_at
        or now >= web_session.absolute_expires_at
    ):
        raise _unauthorized()

    user = session.scalar(
        select(User).where(
            User.id == web_session.user_id,
            User.is_active.is_(True),
            User.role.in_(PORTAL_ROLES),
        )
    )
    if user is None:
        raise _unauthorized()

    touch_after = web_session.last_seen_at + timedelta(
        seconds=settings.web_session_touch_interval_seconds
    )
    if now >= touch_after:
        web_session.last_seen_at = now
        web_session.idle_expires_at = min(
            now + timedelta(seconds=settings.web_session_idle_ttl_seconds),
            web_session.absolute_expires_at,
        )
        web_session.last_ip_hash = _keyed_hash(
            _request_ip(request),
            purpose="ip",
            settings=settings,
        )
        session.commit()

    return PortalSessionContext(
        identity=RequestIdentity(
            user_id=user.id,
            telegram_user_id=user.telegram_user_id,
            role=user.role,
            request_id=_request_id(),
        ),
        web_session=web_session,
    )


def require_portal_session_identity(
    session: Session,
    request: Request,
) -> RequestIdentity:
    return require_portal_session_context(session, request).identity


def resolve_effective_owner(
    session: Session,
    context: PortalSessionContext,
) -> uuid.UUID:
    identity = context.identity
    if identity.role == UserRole.master:
        return identity.user_id
    if identity.role != UserRole.admin:
        raise _unauthorized()

    target_owner_user_id = context.web_session.target_owner_user_id
    if target_owner_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "select_master_required"},
        )
    master = session.scalar(
        select(User).where(
            User.id == target_owner_user_id,
            User.role == UserRole.master,
            User.is_active.is_(True),
        )
    )
    if master is None:
        context.web_session.target_owner_user_id = None
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "select_master_required"},
        )
    return master.id


def require_effective_owner_identity(
    session: Session,
    request: Request,
) -> RequestIdentity:
    context = require_portal_session_context(session, request)
    owner_user_id = resolve_effective_owner(session, context)
    identity = context.identity
    return RequestIdentity(
        user_id=owner_user_id,
        telegram_user_id=identity.telegram_user_id,
        role=identity.role,
        request_id=identity.request_id,
    )


def select_master_scope(
    session: Session,
    context: PortalSessionContext,
    master_user_id: uuid.UUID,
) -> User:
    identity = context.identity
    if identity.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_required"},
        )
    master = session.scalar(
        select(User).where(
            User.id == master_user_id,
            User.role == UserRole.master,
            User.is_active.is_(True),
        )
    )
    if master is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "active_master_not_found"},
        )

    context.web_session.target_owner_user_id = master.id
    _audit(
        session,
        action="admin.master.scope.enter",
        request_id=identity.request_id,
        object_type="web_session",
        owner_user_id=master.id,
        actor_user_id=identity.user_id,
        object_id=context.web_session.id,
    )
    session.commit()
    return master
