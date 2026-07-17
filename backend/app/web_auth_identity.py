from __future__ import annotations

import hmac
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import get_settings
from app.db import get_db_session
from app.models import User, UserRole

SessionDependency = Annotated[Session, Depends(get_db_session)]


def require_web_approval_identity(
    session: SessionDependency,
    internal_key: str | None = Header(default=None, alias="X-Nails-Internal-Key"),
    telegram_user_id: str | None = Header(default=None, alias="X-Telegram-User-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> RequestIdentity | None:
    settings = get_settings()
    expected_key = settings.internal_api_key.get_secret_value()
    if internal_key is None or not hmac.compare_digest(internal_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized"},
        )

    resolved_request_id = (request_id or str(uuid.uuid4())).strip()
    if not resolved_request_id or len(resolved_request_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_request_id"},
        )

    try:
        parsed_telegram_user_id = int(telegram_user_id or "")
    except ValueError:
        return None
    if parsed_telegram_user_id <= 0:
        return None

    user = session.scalar(
        select(User).where(User.telegram_user_id == parsed_telegram_user_id)
    )
    if user is None or not user.is_active or user.role != UserRole.master:
        return None

    return RequestIdentity(
        user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        role=user.role,
        request_id=resolved_request_id,
    )
