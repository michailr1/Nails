from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.scheduling import ServiceListResponse
from app.schemas.scheduling_catalog_bookings import CatalogBookingCreateRequest
from app.schemas.scheduling_catalog_replace import (
    CatalogReplaceRequest,
    CatalogReplaceResponse,
)
from app.schemas.scheduling_management import ClientCreateRequest, ClientReplaceRequest
from app.schemas.web_read import (
    WebBookingCreateResponse,
    WebCalendarResponse,
    WebClientCard,
    WebClientCreateRequest,
    WebClientCreateResponse,
    WebClientListResponse,
    WebClientReplaceRequest,
    WebClientReplaceResponse,
)
from app.services.scheduling_bookings import create_booking
from app.services.scheduling_catalog_replace import replace_catalog
from app.services.scheduling_clients import create_or_reuse_client, replace_client
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_lookup import get_active_client, get_active_client_by_id
from app.services.scheduling_services import list_services
from app.services.web_auth import require_web_session_identity, validate_web_boundary
from app.services.web_export import export_all_calendar, export_calendar, export_clients
from app.services.web_read import (
    list_calendar,
    list_clients,
    web_booking_summary,
    web_client_card,
)

router = APIRouter(prefix="/web/api", tags=["web-read"])
SessionDependency = Annotated[Session, Depends(get_db_session)]


def require_web_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_web_session_identity(session, request)


IdentityDependency = Annotated[RequestIdentity, Depends(require_web_identity)]
ExportFormat = Literal["csv", "xlsx"]


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


def _calendar(
    session: Session,
    identity: RequestIdentity,
    date_from: date,
    date_to: date,
) -> WebCalendarResponse:
    try:
        return list_calendar(
            session,
            identity,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc


@router.get("/calendar", response_model=WebCalendarResponse)
def calendar(
    session: SessionDependency,
    identity: IdentityDependency,
    date_from: date,
    date_to: date,
) -> WebCalendarResponse:
    return _calendar(session, identity, date_from, date_to)


@router.get("/clients", response_model=WebClientListResponse)
def clients(
    session: SessionDependency,
    identity: IdentityDependency,
) -> WebClientListResponse:
    return list_clients(session, identity)


@router.post("/clients", response_model=WebClientCreateResponse)
def client_create(
    body: WebClientCreateRequest,
    request: Request,
    session: SessionDependency,
    identity: IdentityDependency,
) -> WebClientCreateResponse:
    validate_web_boundary(request)
    try:
        result = create_or_reuse_client(
            session,
            identity,
            ClientCreateRequest(
                public_name=body.public_name,
                phone=body.phone,
            ),
        )
        client = get_active_client(session, identity.user_id, body.public_name)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
    return WebClientCreateResponse(
        client=web_client_card(client),
        created=result.created,
        contact_added=result.contact_added,
    )


@router.get("/clients/{client_id}", response_model=WebClientCard)
def client_card(
    client_id: uuid.UUID,
    session: SessionDependency,
    identity: IdentityDependency,
) -> WebClientCard:
    try:
        client = get_active_client_by_id(session, identity.user_id, client_id)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
    return web_client_card(client)


@router.put("/clients/{client_id}", response_model=WebClientReplaceResponse)
def client_replace(
    client_id: uuid.UUID,
    body: WebClientReplaceRequest,
    request: Request,
    session: SessionDependency,
    identity: IdentityDependency,
) -> WebClientReplaceResponse:
    validate_web_boundary(request)
    try:
        current = get_active_client_by_id(session, identity.user_id, client_id)
        result = replace_client(
            session,
            identity,
            ClientReplaceRequest(
                current_public_name=current.public_name,
                public_name=body.public_name,
                phone=body.phone,
                private_alias=current.private_alias,
                contact_channel=body.contact_channel,
                birthday=body.birthday,
                notes=body.notes,
                nail_skin_notes=body.nail_skin_notes,
                sensitivity_notes=body.sensitivity_notes,
                style_preferences=body.style_preferences,
                communication_preferences=body.communication_preferences,
            ),
        )
        updated = get_active_client_by_id(session, identity.user_id, client_id)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
    return WebClientReplaceResponse(
        client=web_client_card(updated),
        changed=result.changed,
        changed_fields=result.changed_fields,
    )


@router.get("/services", response_model=ServiceListResponse)
def services(
    session: SessionDependency,
    identity: IdentityDependency,
) -> ServiceListResponse:
    return list_services(session, identity, include_inactive=True)


@router.put("/services/catalog", response_model=CatalogReplaceResponse)
def service_catalog_replace(
    body: CatalogReplaceRequest,
    request: Request,
    session: SessionDependency,
    identity: IdentityDependency,
) -> CatalogReplaceResponse:
    validate_web_boundary(request)
    return replace_catalog(session, identity, body)


@router.post("/bookings", response_model=WebBookingCreateResponse)
def booking_create(
    body: CatalogBookingCreateRequest,
    request: Request,
    session: SessionDependency,
    identity: IdentityDependency,
) -> WebBookingCreateResponse:
    validate_web_boundary(request)
    try:
        client = get_active_client(
            session,
            identity.user_id,
            body.client_public_name,
        )
        result = create_booking(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
    return WebBookingCreateResponse(
        booking=web_booking_summary(result.booking, client_id=client.id),
        created=result.created,
    )


@router.post("/exports/calendar")
def calendar_export(
    session: SessionDependency,
    identity: IdentityDependency,
    date_from: date,
    date_to: date,
    format_name: Annotated[ExportFormat, Query(alias="format")] = "csv",
) -> Response:
    try:
        exported = export_calendar(
            session,
            identity,
            date_from=date_from,
            date_to=date_to,
            format_name=format_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )


@router.post("/exports/calendar/all")
def all_calendar_export(
    session: SessionDependency,
    identity: IdentityDependency,
    format_name: Annotated[ExportFormat, Query(alias="format")] = "csv",
) -> Response:
    try:
        exported = export_all_calendar(
            session,
            identity,
            format_name=format_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )


@router.post("/exports/clients")
def clients_export(
    session: SessionDependency,
    identity: IdentityDependency,
    format_name: Annotated[ExportFormat, Query(alias="format")] = "csv",
) -> Response:
    exported = export_clients(
        session,
        identity,
        format_name=format_name,
    )
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )
