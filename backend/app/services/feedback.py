from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import get_settings
from app.feedback_models import FeedbackEvent
from app.models import UserRole
from app.schemas.feedback import FeedbackCreateRequest

_MAX_MESSAGES = 4
_MAX_CONTENT_LENGTH = 500
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SECRET_RE = re.compile(
    r"(?i)\b(api[_ -]?key|token|secret|password|authorization)\b\s*[:=]\s*\S+"
)
_TECHNICAL_RE = re.compile(
    r"(?i)(traceback|stdout|stderr|tool trace|/opt/|/root/|/etc/|x-nails-internal-key)"
)


def _require_admin(identity: RequestIdentity) -> None:
    if identity.role is not UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "forbidden"})


def _mask_text(value: str) -> str:
    compact = " ".join(value.split())[:_MAX_CONTENT_LENGTH]
    compact = _EMAIL_RE.sub("[email]", compact)
    compact = _PHONE_RE.sub("[phone]", compact)
    compact = _SECRET_RE.sub("[secret]", compact)
    compact = _TECHNICAL_RE.sub("[technical]", compact)
    return compact.strip()


def sanitize_context(body: FeedbackCreateRequest) -> list[dict[str, str]]:
    safe: list[dict[str, str]] = []
    for message in body.context[-_MAX_MESSAGES:]:
        content = _mask_text(message.content)
        if content:
            safe.append({"role": message.role, "content": content})
    if not safe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "empty_safe_context"},
        )
    return safe


def purge_expired_feedback(session: Session) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().feedback_retention_days)
    result = session.execute(delete(FeedbackEvent).where(FeedbackEvent.created_at < cutoff))
    return int(result.rowcount or 0)


def save_feedback(
    session: Session,
    identity: RequestIdentity,
    body: FeedbackCreateRequest,
) -> FeedbackEvent:
    purge_expired_feedback(session)
    event = FeedbackEvent(
        owner_user_id=identity.user_id,
        actor_user_id=identity.user_id,
        kind=body.kind,
        safe_context=sanitize_context(body),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def list_feedback(session: Session, identity: RequestIdentity, limit: int) -> list[FeedbackEvent]:
    _require_admin(identity)
    purged = purge_expired_feedback(session)
    if purged:
        session.commit()
    return list(
        session.scalars(
            select(FeedbackEvent)
            .order_by(FeedbackEvent.created_at.desc())
            .limit(limit)
        )
    )


def delete_feedback(
    session: Session,
    identity: RequestIdentity,
    event_id: uuid.UUID,
) -> bool:
    _require_admin(identity)
    event = session.get(FeedbackEvent, event_id)
    if event is None:
        return False
    session.delete(event)
    session.commit()
    return True
