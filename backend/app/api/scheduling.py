from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import RequestIdentity, require_request_identity
from app.db import get_db_session
from app.schemas.scheduling import (
    AvailabilityReplaceRequest,
    AvailabilityReplaceResponse,
    BookingCreateRequest,
    BookingCreateResponse,
    ClientCreateRequest,
    ClientCreateResponse,
    ClientLookupResponse,
    DateResolveRequest,
    DateResolveResponse,
    DayViewResponse,
    FreeSlotsResponse,
    ServiceListResponse,
)
from app.services.scheduling_availability import replace_availability
from app.services.scheduling_bookings import create_booking
from app.services.scheduling_clients import create_or_reuse_client
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_dates import resolve_date
from app.services.scheduling_lookup import find_client_exact, list_active_services
from app.services.scheduling_queries import find_free_slots, get_day_view

router = APIRouter(prefix="/api/v1/scheduling", tags=["scheduling"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
IdentityDependency = Annotated[RequestIdentity, Depends(require_request_identity)]


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.post("/date/resolve", response_model=DateResolveResponse)
def date_resolve(
    body: DateResolveRequest,
    identity: IdentityDependency,
) -> DateResolveResponse:
    del identity
    return resolve_date(body)


@router.get("/services", response_model=ServiceListResponse)
def services(
    session: SessionDependency,
    identity: IdentityDependency,
) -> ServiceListResponse:
    return list_active_services(session, identity)


@router.get("/clients/exact", response_model=ClientLookupResponse)
def client_exact(
    session: SessionDependency,
    identity: IdentityDependency,
    public_name: Annotated[str, Query(min_length=1, max_length=160)],
) -> ClientLookupResponse:
    return find_client_exact(session, identity, public_name)


@router.post("/clients", response_model=ClientCreateResponse)
def create_client(
    body: ClientCreateRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> ClientCreateResponse:
    try:
        return create_or_reuse_client(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get("/day", response_model=DayViewResponse)
def day_view(
    session: SessionDependency,
    identity: IdentityDependency,
    day: date,
) -> DayViewResponse:
    return get_day_view(session, identity, day)


@router.get("/slots", response_model=FreeSlotsResponse)
def slots(
    session: SessionDependency,
    identity: IdentityDependency,
    day: date,
    service_name: Annotated[str, Query(min_length=1, max_length=160)],
) -> FreeSlotsResponse:
    try:
        return find_free_slots(session, identity, day, service_name)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.put("/availability", response_model=AvailabilityReplaceResponse)
def availability_replace(
    body: AvailabilityReplaceRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> AvailabilityReplaceResponse:
    try:
        return replace_availability(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post("/bookings", response_model=BookingCreateResponse)
def booking_create(
    body: BookingCreateRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> BookingCreateResponse:
    try:
        return create_booking(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
