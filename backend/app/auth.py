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


@dataclass(frozen=True, slots=True)
class ClientRequestIdentity:
    owner_user_id: uuid.UUID
    telegram_user_id: int
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


def _parse_telegram_user_id(value: str | None) -> int:
    try:
        parsed = int(value or "")
    except ValueError as exc:
        raise _unauthorized() from exc
    if parsed <= 0:
        raise _unauthorized()
    return parsed


def _resolve_request_id(value: str | None) -> str:
    request_id = (value or str(uuid.uuid4())).strip()
    if not request_id or len(request_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_request_id"},
        )
    return request_id


def require_internal_key(
    internal_key: str | None = Header(default=None, alias="X-Nails-Internal-Key"),
) -> None:
    expected_key = get_settings().internal_api_key.get_secret_value()
    if internal_key is None or not hmac.compare_digest(internal_key, expected_key):
        raise _unauthorized()


def require_client_internal_key(
    internal_key: str | None = Header(
        default=None,
        alias="X-Nails-Client-Internal-Key",
    ),
) -> None:
    settings = get_settings()
    if not settings.client_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found"},
        )
    expected_key = settings.client_internal_api_key.get_secret_value()
    if internal_key is None or not hmac.compare_digest(internal_key, expected_key):
        raise _unauthorized()


def require_request_identity(
    session: SessionDependency,
    _: Annotated[None, Depends(require_internal_key)],
    telegram_user_id: str | None = Header(default=None, alias="X-Telegram-User-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> RequestIdentity:
    parsed_telegram_user_id = _parse_telegram_user_id(telegram_user_id)
    resolved_request_id = _resolve_request_id(request_id)

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


def require_client_request_identity(
    session: SessionDependency,
    _: Annotated[None, Depends(require_client_internal_key)],
    telegram_user_id: str | None = Header(default=None, alias="X-Telegram-User-ID"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ClientRequestIdentity:
    settings = get_settings()
    parsed_telegram_user_id = _parse_telegram_user_id(telegram_user_id)
    resolved_request_id = _resolve_request_id(request_id)
    owner_telegram_user_id = settings.client_owner_telegram_user_id
    if owner_telegram_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "client_owner_unavailable"},
        )

    owner = session.scalar(
        select(User).where(
            User.telegram_user_id == owner_telegram_user_id,
            User.is_active.is_(True),
        )
    )
    if owner is None or owner.role not in {UserRole.admin, UserRole.master}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "client_owner_unavailable"},
        )

    return ClientRequestIdentity(
        owner_user_id=owner.id,
        telegram_user_id=parsed_telegram_user_id,
        request_id=resolved_request_id,
    )
