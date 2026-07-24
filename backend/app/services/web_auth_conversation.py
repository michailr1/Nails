from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import get_settings
from app.models import UserRole
from app.services.web_auth import _consume_rate_bucket, _raise_rate_limited
from app.web_auth_models import WebChallengeStatus, WebLoginChallenge


@dataclass(frozen=True, slots=True)
class ConversationalChallenge:
    status: str
    expires_at: datetime | None
    remaining_seconds: int


def _now() -> datetime:
    return datetime.now(UTC)


def _number_hash(verification_number: str) -> str:
    settings = get_settings()
    key = settings.web_auth_hmac_key.get_secret_value().encode("utf-8")
    message = f"challenge-number\x1f{verification_number}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _identity_scope(identity: RequestIdentity) -> str:
    return hashlib.sha256(str(identity.user_id).encode()).hexdigest()


def _enforce_rate_limit(
    session: Session,
    *,
    identity: RequestIdentity,
    action: str,
    limit: int,
    now: datetime,
) -> None:
    allowed = _consume_rate_bucket(
        session,
        action=action,
        scope_hash=_identity_scope(identity),
        limit=limit,
        window_seconds=60,
        now=now,
    )
    if not allowed:
        _raise_rate_limited(session)


def _view(challenge: WebLoginChallenge | None, now: datetime) -> ConversationalChallenge:
    if challenge is None:
        return ConversationalChallenge("not_found", None, 0)
    remaining = max(0, int((challenge.expires_at - now).total_seconds()))
    return ConversationalChallenge(challenge.status, challenge.expires_at, remaining)


def _can_approve_web_login(identity: RequestIdentity) -> bool:
    return identity.role in {UserRole.master, UserRole.admin}


def inspect_conversational_challenge(
    session: Session,
    *,
    identity: RequestIdentity,
    verification_number: str,
) -> ConversationalChallenge:
    if not _can_approve_web_login(identity):
        return ConversationalChallenge("not_found", None, 0)

    now = _now()
    _enforce_rate_limit(
        session,
        identity=identity,
        action="conversation_read",
        limit=12,
        now=now,
    )
    challenge = session.scalar(
        select(WebLoginChallenge)
        .where(WebLoginChallenge.code_hash == _number_hash(verification_number))
        .with_for_update()
    )
    if challenge is None:
        session.commit()
        return _view(None, now)

    if (
        challenge.status
        in {
            WebChallengeStatus.pending.value,
            WebChallengeStatus.approved.value,
        }
        and now >= challenge.expires_at
    ):
        challenge.status = WebChallengeStatus.expired.value

    if challenge.user_id is not None and challenge.user_id != identity.user_id:
        session.commit()
        return _view(None, now)

    if challenge.user_id is None:
        if challenge.status == WebChallengeStatus.expired.value:
            session.commit()
            return _view(challenge, now)
        if challenge.status != WebChallengeStatus.pending.value:
            session.commit()
            return _view(None, now)
        challenge.user_id = identity.user_id

    session.commit()
    return _view(challenge, now)


def decide_conversational_challenge(
    session: Session,
    *,
    identity: RequestIdentity,
    verification_number: str,
    decision: Literal["approve", "deny"],
) -> ConversationalChallenge:
    if not _can_approve_web_login(identity):
        return ConversationalChallenge("not_found", None, 0)

    now = _now()
    _enforce_rate_limit(
        session,
        identity=identity,
        action="conversation_decision",
        limit=6,
        now=now,
    )
    challenge = session.scalar(
        select(WebLoginChallenge)
        .where(WebLoginChallenge.code_hash == _number_hash(verification_number))
        .with_for_update()
    )
    if challenge is None:
        session.commit()
        return _view(None, now)

    if (
        challenge.status
        in {
            WebChallengeStatus.pending.value,
            WebChallengeStatus.approved.value,
        }
        and now >= challenge.expires_at
    ):
        challenge.status = WebChallengeStatus.expired.value

    if challenge.user_id is not None and challenge.user_id != identity.user_id:
        session.commit()
        return _view(None, now)

    if challenge.user_id is None:
        if challenge.status == WebChallengeStatus.expired.value:
            session.commit()
            return _view(challenge, now)
        if challenge.status != WebChallengeStatus.pending.value:
            session.commit()
            return _view(None, now)
        challenge.user_id = identity.user_id

    if decision == "approve":
        if challenge.status == WebChallengeStatus.pending.value:
            challenge.status = WebChallengeStatus.approved.value
            challenge.approved_at = now
    elif challenge.status == WebChallengeStatus.pending.value:
        challenge.status = WebChallengeStatus.denied.value

    session.commit()
    return _view(challenge, now)
