from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

from fastapi import Request
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import get_settings
from app.web_auth_models import WebAuthRateBucket


def _scope_hash(value: str, *, purpose: str) -> str:
    settings = get_settings()
    key = settings.web_auth_hmac_key.get_secret_value().encode("utf-8")
    message = f"{purpose}\x1f{value}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


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
    client_ip = request.client.host if request.client is not None else "unknown"
    _ensure_bucket(
        session,
        action="challenge_start",
        scope_hash=_scope_hash(client_ip, purpose="ip"),
        now=now,
    )


def ensure_approval_bucket(
    session: Session,
    identity: RequestIdentity,
    now: datetime,
) -> None:
    _ensure_bucket(
        session,
        action="challenge_approve",
        scope_hash=_scope_hash(str(identity.user_id), purpose="approve-account"),
        now=now,
    )
