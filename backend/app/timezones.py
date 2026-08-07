from __future__ import annotations

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings


def configured_timezone_name() -> str:
    return get_settings().app_timezone


def validate_timezone_name(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("timezone_required")
    if len(candidate) > 64:
        raise ValueError("timezone_too_long")
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone_unknown") from exc
    return candidate


def timezone_from_name(value: str | None) -> ZoneInfo:
    return ZoneInfo(validate_timezone_name(value or configured_timezone_name()))


def owner_timezone_name(session: Session, owner_user_id: uuid.UUID) -> str:
    stored = session.execute(
        text("SELECT timezone FROM users WHERE id = :owner_user_id"),
        {"owner_user_id": str(owner_user_id)},
    ).scalar_one_or_none()
    return validate_timezone_name(stored or configured_timezone_name())


def owner_timezone(session: Session, owner_user_id: uuid.UUID) -> ZoneInfo:
    return ZoneInfo(owner_timezone_name(session, owner_user_id))
