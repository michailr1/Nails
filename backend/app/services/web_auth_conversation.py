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


def _view(challenge: WebLoginChallenge | None, now: datetime) -> ConversationalChallenge:
    if challenge is None:
        return ConversationalChallenge("not_found", None, 0)
    remaining = max(0, int((challenge.expires_at - now).total_seconds()))
    return ConversationalChallenge(challenge.status, challenge.expires_at, remaining)


def inspect_conversational_challenge(
    session: Session,
    *,
    identity: RequestIdentity,
    verification_number: str,
) -> ConversationalChallenge:
    if identity.role != UserRole.master:
        return ConversationalChallenge("not_found", None, 0)

    now = _now()
    challenge = session.scalar(
        select(WebLoginChallenge)
        .where(WebLoginChallenge.code_hash == _number_hash(verification_number))
        .with_for_update()
    )
    if challenge is None:
        session.commit()
        return _view(None, now)

    if (
        challenge.status in {
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
    if identity.role != UserRole.master:
        return ConversationalChallenge("not_found", None, 0)

    now = _now()
    challenge = session.scalar(
        select(WebLoginChallenge)
        .where(WebLoginChallenge.code_hash == _number_hash(verification_number))
        .with_for_update()
    )
    if challenge is None or challenge.user_id != identity.user_id:
        session.commit()
        return _view(None, now)

    if (
        challenge.status in {
            WebChallengeStatus.pending.value,
            WebChallengeStatus.approved.value,
        }
        and now >= challenge.expires_at
    ):
        challenge.status = WebChallengeStatus.expired.value

    if decision == "approve":
        if challenge.status == WebChallengeStatus.pending.value:
            challenge.status = WebChallengeStatus.approved.value
            challenge.approved_at = now
    elif challenge.status == WebChallengeStatus.pending.value:
        challenge.status = WebChallengeStatus.denied.value

    session.commit()
    return _view(challenge, now)
