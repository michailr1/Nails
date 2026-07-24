from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import Settings, get_settings
from app.models import AuditEvent, User, UserRole
from app.web_auth_models import (
    WebAuthRateBucket,
    WebChallengeStatus,
    WebLoginChallenge,
    WebSession,
)

_SESSION_COOKIE = "__Host-nails_session"
_LOGIN_COOKIE = "__Host-nails_login"


@dataclass(frozen=True, slots=True)
class StartedChallenge:
    challenge: WebLoginChallenge
    verification_number: str
    browser_token: str


@dataclass(frozen=True, slots=True)
class ChallengeStatusView:
    challenge_id: uuid.UUID
    status: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ConsumedChallenge:
    authenticated: bool
    status: str
    session_token: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _settings() -> Settings:
    settings = get_settings()
    if not settings.web_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "web_auth_unavailable"},
        )
    return settings


def _keyed_hash(
    value: str,
    *,
    purpose: str,
    settings: Settings | None = None,
) -> str:
    active_settings = settings or _settings()
    key = active_settings.web_auth_hmac_key.get_secret_value().encode("utf-8")
    message = f"{purpose}\x1f{value}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _request_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _request_id() -> str:
    return str(uuid.uuid4())


def _user_agent_hash(request: Request, settings: Settings) -> str | None:
    value = request.headers.get("user-agent", "").strip()
    if not value:
        return None
    return _keyed_hash(
        value[:512],
        purpose="user-agent",
        settings=settings,
    )


def _pending_scope_hash(
    request_ip_hash: str,
    user_agent_hash: str | None,
) -> str:
    fingerprint = f"{request_ip_hash}:{user_agent_hash or '-'}"
    return hashlib.sha256(fingerprint.encode()).hexdigest()


def _advisory_lock_key(scope_hash: str) -> int:
    raw = int(scope_hash[:16], 16)
    return raw if raw < 2**63 else raw - 2**64


def validate_web_boundary(request: Request) -> None:
    settings = _settings()
    host = request.headers.get("host", "").split(":", 1)[0].strip().lower()
    if host not in settings.allowed_web_hosts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_host"},
        )

    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.allowed_web_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "invalid_origin"},
        )
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "origin_required"},
        )


def _audit(
    session: Session,
    *,
    action: str,
    request_id: str,
    object_type: str,
    owner_user_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    object_id: uuid.UUID | None = None,
    safe_changes: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            owner_user_id=owner_user_id,
            actor_user_id=actor_user_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            request_id=request_id,
            safe_changes=safe_changes or {},
        )
    )


def _ensure_rate_bucket(
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


def _consume_rate_bucket(
    session: Session,
    *,
    action: str,
    scope_hash: str,
    limit: int,
    window_seconds: int,
    now: datetime,
) -> bool:
    _ensure_rate_bucket(
        session,
        action=action,
        scope_hash=scope_hash,
        now=now,
    )
    bucket = session.scalar(
        select(WebAuthRateBucket)
        .where(
            WebAuthRateBucket.action == action,
            WebAuthRateBucket.scope_hash == scope_hash,
        )
        .with_for_update()
    )
    if bucket is None:
        raise RuntimeError("rate bucket upsert did not produce a row")

    if now >= bucket.window_started_at + timedelta(seconds=window_seconds):
        bucket.window_started_at = now
        bucket.count = 1
        return True
    if bucket.count >= limit:
        return False

    bucket.count += 1
    return True


def _raise_rate_limited(session: Session) -> None:
    session.commit()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "rate_limited"},
    )


def _replace_pending_challenge(
    session: Session,
    *,
    pending_scope_hash: str,
) -> None:
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
    if challenges:
        session.flush()


def start_challenge(session: Session, request: Request) -> StartedChallenge:
    validate_web_boundary(request)
    settings = _settings()
    now = _now()
    request_id = _request_id()
    request_ip_hash = _keyed_hash(
        _request_ip(request),
        purpose="ip",
        settings=settings,
    )
    user_agent_hash = _user_agent_hash(request, settings)
    pending_scope_hash = _pending_scope_hash(
        request_ip_hash,
        user_agent_hash,
    )

    if not _consume_rate_bucket(
        session,
        action="challenge_start",
        scope_hash=request_ip_hash,
        limit=settings.web_rate_start_limit,
        window_seconds=settings.web_rate_start_window_seconds,
        now=now,
    ):
        _audit(
            session,
            action="web_login_rate_limited",
            request_id=request_id,
            object_type="web_login_challenge",
            safe_changes={"scope": "ip", "operation": "start"},
        )
        _raise_rate_limited(session)

    _replace_pending_challenge(
        session,
        pending_scope_hash=pending_scope_hash,
    )

    browser_token = secrets.token_urlsafe(32)
    challenge: WebLoginChallenge | None = None
    verification_number = ""

    for _ in range(8):
        verification_number = f"{secrets.randbelow(1_000_000):06d}"
        candidate = WebLoginChallenge(
            code_hash=_keyed_hash(
                verification_number,
                purpose="challenge-number",
                settings=settings,
            ),
            browser_token_hash=_keyed_hash(
                browser_token,
                purpose="login-token",
                settings=settings,
            ),
            pending_scope_hash=pending_scope_hash,
            status=WebChallengeStatus.pending.value,
            attempt_count=0,
            max_attempts=settings.web_challenge_max_attempts,
            request_ip_hash=request_ip_hash,
            user_agent_hash=user_agent_hash,
            request_id=request_id,
            expires_at=now
            + timedelta(seconds=settings.web_challenge_ttl_seconds),
        )
        nested = session.begin_nested()
        session.add(candidate)
        try:
            session.flush()
            nested.commit()
            challenge = candidate
            break
        except IntegrityError:
            nested.rollback()

    if challenge is None:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "challenge_unavailable"},
        )

    _audit(
        session,
        action="web_login_challenge_started",
        request_id=request_id,
        object_type="web_login_challenge",
        object_id=challenge.id,
    )
    session.commit()
    session.refresh(challenge)
    return StartedChallenge(
        challenge=challenge,
        verification_number=verification_number,
        browser_token=browser_token,
    )


def set_start_cookies(response: Response, started: StartedChallenge) -> None:
    response.set_cookie(
        _LOGIN_COOKIE,
        started.browser_token,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
        max_age=600,
    )


def challenge_status(
    session: Session,
    request: Request,
    challenge_id: uuid.UUID,
) -> ChallengeStatusView:
    validate_web_boundary(request)
    settings = _settings()
    now = _now()
    rate_scope = _keyed_hash(
        f"{challenge_id}:{_request_ip(request)}",
        purpose="status-scope",
        settings=settings,
    )
    if not _consume_rate_bucket(
        session,
        action="challenge_status",
        scope_hash=rate_scope,
        limit=settings.web_rate_status_limit,
        window_seconds=settings.web_rate_status_window_seconds,
        now=now,
    ):
        _raise_rate_limited(session)

    challenge = session.get(WebLoginChallenge, challenge_id)
    login_token = request.cookies.get(_LOGIN_COOKIE, "")
    if challenge is None or not login_token:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "challenge_not_found"},
        )
    supplied_hash = _keyed_hash(
        login_token,
        purpose="login-token",
        settings=settings,
    )
    if not hmac.compare_digest(supplied_hash, challenge.browser_token_hash):
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "challenge_not_found"},
        )

    effective_status = challenge.status
    if (
        challenge.status
        in {
            WebChallengeStatus.pending.value,
            WebChallengeStatus.approved.value,
        }
        and now >= challenge.expires_at
    ):
        effective_status = WebChallengeStatus.expired.value
    session.commit()
    return ChallengeStatusView(
        challenge_id=challenge.id,
        status=effective_status,
        expires_at=challenge.expires_at,
    )


def approve_challenge(
    session: Session,
    *,
    identity: RequestIdentity,
    challenge_id: uuid.UUID,
    verification_number: str,
) -> bool:
    settings = _settings()
    if identity.role not in {UserRole.master, UserRole.admin}:
        return False

    now = _now()
    account_scope = _keyed_hash(
        str(identity.user_id),
        purpose="approve-account",
        settings=settings,
    )
    server_scope = _keyed_hash(
        "internal-api",
        purpose="approve-server",
        settings=settings,
    )
    account_allowed = _consume_rate_bucket(
        session,
        action="challenge_approve",
        scope_hash=account_scope,
        limit=settings.web_rate_approve_limit,
        window_seconds=settings.web_rate_approve_window_seconds,
        now=now,
    )
    server_allowed = _consume_rate_bucket(
        session,
        action="challenge_approve_server",
        scope_hash=server_scope,
        limit=settings.web_rate_approve_server_limit,
        window_seconds=settings.web_rate_approve_window_seconds,
        now=now,
    )
    if not account_allowed or not server_allowed:
        _audit(
            session,
            action="web_login_rate_limited",
            request_id=identity.request_id,
            object_type="web_login_challenge",
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            safe_changes={"scope": "approval", "operation": "tap-approve"},
        )
        session.commit()
        return False

    challenge = session.scalar(
        select(WebLoginChallenge)
        .where(WebLoginChallenge.id == challenge_id)
        .with_for_update()
    )
    if challenge is None:
        session.commit()
        return False

    if (
        now >= challenge.expires_at
        and challenge.status == WebChallengeStatus.pending.value
    ):
        challenge.status = WebChallengeStatus.expired.value
    if challenge.status != WebChallengeStatus.pending.value:
        session.commit()
        return False

    supplied_hash = _keyed_hash(
        verification_number,
        purpose="challenge-number",
        settings=settings,
    )
    if not hmac.compare_digest(supplied_hash, challenge.code_hash):
        challenge.attempt_count += 1
        if challenge.attempt_count >= challenge.max_attempts:
            challenge.status = WebChallengeStatus.locked.value
        session.commit()
        return False

    challenge.user_id = identity.user_id
    challenge.status = WebChallengeStatus.approved.value
    challenge.approved_at = now
    _audit(
        session,
        action="web_login_challenge_approved",
        request_id=identity.request_id,
        object_type="web_login_challenge",
        owner_user_id=identity.user_id,
        actor_user_id=identity.user_id,
        object_id=challenge.id,
        safe_changes={"method": "telegram_tap_approve"},
    )
    session.commit()
    return True


def consume_challenge(
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
            User.role == UserRole.master,
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


def set_session_cookie(
    response: Response,
    session_token: str,
    settings: Settings | None = None,
) -> None:
    active_settings = settings or _settings()
    response.set_cookie(
        _SESSION_COOKIE,
        session_token,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=active_settings.web_session_absolute_ttl_seconds,
    )
    response.delete_cookie(
        _LOGIN_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        _SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        _LOGIN_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthorized"},
    )


def require_web_session_identity(
    session: Session,
    request: Request,
) -> RequestIdentity:
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
            User.role == UserRole.master,
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

    return RequestIdentity(
        user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        role=user.role,
        request_id=_request_id(),
    )


def logout_web_session(session: Session, request: Request) -> bool:
    validate_web_boundary(request)
    settings = _settings()
    token = request.cookies.get(_SESSION_COOKIE, "")
    if not token:
        return True

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
    if web_session is None or web_session.revoked_at is not None:
        return True

    web_session.revoked_at = _now()
    _audit(
        session,
        action="web_session_revoked",
        request_id=_request_id(),
        object_type="web_session",
        owner_user_id=web_session.user_id,
        actor_user_id=web_session.user_id,
        object_id=web_session.id,
    )
    session.commit()
    return True
