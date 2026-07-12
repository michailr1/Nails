import hmac
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db_session
from app.models import User, UserRole

SessionDependency = Annotated[Session, Depends(get_db_session)]


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    user_id: uuid.UUID
    telegram_user_id: int
    role: UserRole
    request_id: str


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthorized"},
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "forbidden"},
    )


def require_request_identity(
    session: SessionDependency,
    internal_key: str | None = Header(default=None, alias="X-Nails-Internal-Key"),
    telegram_user_id: str | None = Header(default=None, alias="X-Telegram-User-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> RequestIdentity:
    settings = get_settings()
    expected_key = settings.internal_api_key.get_secret_value()

    if internal_key is None or not hmac.compare_digest(internal_key, expected_key):
        raise _unauthorized()

    try:
        parsed_telegram_user_id = int(telegram_user_id or "")
    except ValueError as exc:
        raise _unauthorized() from exc

    if parsed_telegram_user_id <= 0:
        raise _unauthorized()

    resolved_request_id = (request_id or str(uuid.uuid4())).strip()
    if not resolved_request_id or len(resolved_request_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_request_id"},
        )

    user = session.scalar(
        select(User).where(
            User.telegram_user_id == parsed_telegram_user_id,
            User.is_active.is_(True),
        )
    )
    if user is None or user.role not in {UserRole.admin, UserRole.master}:
        raise _forbidden()

    return RequestIdentity(
        user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        role=user.role,
        request_id=resolved_request_id,
    )
