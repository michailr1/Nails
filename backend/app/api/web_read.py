from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.web_read import WebCalendarResponse, WebClientCard, WebClientListResponse
from app.services.web_auth import require_web_session_identity
from app.services.web_export import export_all_calendar, export_calendar, export_clients
from app.services.web_read import list_calendar, list_clients

router = APIRouter(prefix="/web/api", tags=["web-read"])
SessionDependency = Annotated[Session, Depends(get_db_session)]


def require_web_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_web_session_identity(session, request)


IdentityDependency = Annotated[RequestIdentity, Depends(require_web_identity)]
ExportFormat = Literal["csv", "xlsx"]


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


@router.get("/clients/{client_id}", response_model=WebClientCard)
def client_card(
    client_id: uuid.UUID,
    session: SessionDependency,
    identity: IdentityDependency,
) -> WebClientCard:
    data = list_clients(session, identity)
    for client in data.clients:
        if client.client_id == client_id:
            return client
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "client_not_found"},
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
