import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    ClientTransportIdentity,
    RequestIdentity,
    require_client_transport_identity,
    require_request_identity,
)
from app.db import get_db_session
from app.schemas.client_booking_requests import (
    BookingRequestListResponse,
    BookingRequestPublic,
    ClientBookingRequestCreate,
)
from app.services.client_booking_requests import (
    approve_master_booking_request,
    cancel_client_booking_request,
    create_client_booking_request,
    list_client_booking_requests,
    list_master_booking_requests,
    reject_master_booking_request,
)
from app.services.client_contour import require_client_binding
from app.services.scheduling_common import SchedulingDomainError

router = APIRouter(tags=["client-booking-requests"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
ClientIdentityDependency = Annotated[
    ClientTransportIdentity,
    Depends(require_client_transport_identity),
]
TrustedIdentityDependency = Annotated[RequestIdentity, Depends(require_request_identity)]
BindingHeader = Annotated[str, Header(alias="X-Client-Binding-ID", min_length=1)]


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


def _uuid(value: str, *, code: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": code}) from exc


def _public(row) -> BookingRequestPublic:
    return BookingRequestPublic(
        id=row.id,
        status=row.status,
        service_name=row.service_name,
        addon_names=list(row.addon_names),
        addon_quantities=dict(row.addon_quantities),
        starts_at=row.starts_at,
        booking_id=row.booking_id,
        created_at=row.created_at,
    )


@router.post("/api/v1/client/requests", response_model=BookingRequestPublic)
def create_request(
    body: ClientBookingRequestCreate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> BookingRequestPublic:
    try:
        context = require_client_binding(
            session,
            identity,
            binding_id=_uuid(binding_header, code="invalid_client_binding_id"),
        )
        row = create_client_booking_request(
            session,
            identity,
            context,
            service_name=body.service_name,
            addon_names=body.addon_names,
            addon_quantities=body.addon_quantities,
            starts_at=body.starts_at,
            idempotency_key=body.idempotency_key,
        )
        return _public(row)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get("/api/v1/client/requests", response_model=BookingRequestListResponse)
def list_requests(
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> BookingRequestListResponse:
    try:
        context = require_client_binding(
            session,
            identity,
            binding_id=_uuid(binding_header, code="invalid_client_binding_id"),
        )
        rows = list_client_booking_requests(session, context)
        return BookingRequestListResponse(requests=[_public(row) for row in rows])
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post(
    "/api/v1/client/requests/{booking_request_id}/cancel",
    response_model=BookingRequestPublic,
)
def cancel_request(
    booking_request_id: str,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> BookingRequestPublic:
    try:
        context = require_client_binding(
            session,
            identity,
            binding_id=_uuid(binding_header, code="invalid_client_binding_id"),
        )
        return _public(
            cancel_client_booking_request(
                session,
                identity,
                context,
                _uuid(booking_request_id, code="invalid_booking_request_id"),
            )
        )
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get(
    "/api/v1/scheduling/client-requests",
    response_model=BookingRequestListResponse,
)
def master_list_requests(
    session: SessionDependency,
    identity: TrustedIdentityDependency,
) -> BookingRequestListResponse:
    rows = list_master_booking_requests(session, identity)
    return BookingRequestListResponse(requests=[_public(row) for row in rows])


@router.post(
    "/api/v1/scheduling/client-requests/{booking_request_id}/approve",
    response_model=BookingRequestPublic,
)
def master_approve_request(
    booking_request_id: str,
    session: SessionDependency,
    identity: TrustedIdentityDependency,
) -> BookingRequestPublic:
    try:
        return _public(
            approve_master_booking_request(
                session,
                identity,
                _uuid(booking_request_id, code="invalid_booking_request_id"),
            )
        )
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post(
    "/api/v1/scheduling/client-requests/{booking_request_id}/reject",
    response_model=BookingRequestPublic,
)
def master_reject_request(
    booking_request_id: str,
    session: SessionDependency,
    identity: TrustedIdentityDependency,
) -> BookingRequestPublic:
    try:
        return _public(
            reject_master_booking_request(
                session,
                identity,
                _uuid(booking_request_id, code="invalid_booking_request_id"),
            )
        )
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
