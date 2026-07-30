from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.client_booking_requests import (
    BookingRequestListResponse,
    BookingRequestPublic,
    MasterBookingRequestApprove,
)
from app.services.client_booking_requests import (
    approve_master_booking_request,
    list_master_booking_requests,
    reject_master_booking_request,
)
from app.services.scheduling_common import SchedulingDomainError
from app.services.web_auth import require_web_session_identity, validate_web_boundary
from app.services.web_portal_auth import require_effective_owner_identity

router = APIRouter(prefix="/web/api/client-requests", tags=["web-client-requests"])
SessionDependency = Annotated[Session, Depends(get_db_session)]


def require_read_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_effective_owner_identity(session, request)


def require_write_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_web_session_identity(session, request)


ReadIdentityDependency = Annotated[RequestIdentity, Depends(require_read_identity)]
WriteIdentityDependency = Annotated[RequestIdentity, Depends(require_write_identity)]


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


def _public(row) -> BookingRequestPublic:
    return BookingRequestPublic(
        id=row.id,
        status=row.status,
        client_id=row.client_id,
        requested_public_name=row.requested_public_name,
        service_name=row.service_name,
        addon_names=list(row.addon_names),
        addon_quantities=dict(row.addon_quantities),
        starts_at=row.starts_at,
        booking_id=row.booking_id,
        created_at=row.created_at,
    )


@router.get("", response_model=BookingRequestListResponse)
def list_pending_requests(
    session: SessionDependency,
    identity: ReadIdentityDependency,
) -> BookingRequestListResponse:
    rows = list_master_booking_requests(session, identity, status="pending")
    return BookingRequestListResponse(requests=[_public(row) for row in rows])


@router.post("/{booking_request_id}/approve", response_model=BookingRequestPublic)
def approve_request(
    booking_request_id: uuid.UUID,
    body: MasterBookingRequestApprove,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentityDependency,
) -> BookingRequestPublic:
    validate_web_boundary(request)
    try:
        row = approve_master_booking_request(
            session,
            identity,
            booking_request_id,
            resolution=body.resolution,
            selected_client_id=body.client_id,
        )
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
    return _public(row)


@router.post("/{booking_request_id}/reject", response_model=BookingRequestPublic)
def reject_request(
    booking_request_id: uuid.UUID,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentityDependency,
) -> BookingRequestPublic:
    validate_web_boundary(request)
    try:
        row = reject_master_booking_request(
            session,
            identity,
            booking_request_id,
        )
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
    return _public(row)
