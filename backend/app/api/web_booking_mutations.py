from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.scheduling_management import (
    BookingCancelRequest,
    BookingMutationResponse,
    BookingRescheduleRequest,
)
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_management import cancel_booking, reschedule_booking
from app.services.web_auth import require_web_session_identity, validate_web_boundary

router = APIRouter(prefix="/web/api/bookings", tags=["web-booking-mutations"])
SessionDependency = Annotated[Session, Depends(get_db_session)]


def require_web_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_web_session_identity(session, request)


IdentityDependency = Annotated[RequestIdentity, Depends(require_web_identity)]


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.put("/reschedule", response_model=BookingMutationResponse)
def booking_reschedule(
    body: BookingRescheduleRequest,
    request: Request,
    session: SessionDependency,
    identity: IdentityDependency,
) -> BookingMutationResponse:
    validate_web_boundary(request)
    try:
        return reschedule_booking(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.put("/cancel", response_model=BookingMutationResponse)
def booking_cancel(
    body: BookingCancelRequest,
    request: Request,
    session: SessionDependency,
    identity: IdentityDependency,
) -> BookingMutationResponse:
    validate_web_boundary(request)
    try:
        return cancel_booking(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
