from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.preferences import DefaultWorkHoursUpdateRequest, MasterPreferencesResponse
from app.schemas.scheduling import AvailabilityReplaceRequest, AvailabilityReplaceResponse
from app.schemas.scheduling_availability import AvailabilityPreviewResponse
from app.schemas.web_schedule import WebScheduleRangeQuery, WebScheduleResponse
from app.services.preferences import get_master_preferences, save_default_work_hours
from app.services.scheduling_availability import replace_availability
from app.services.scheduling_availability_preview import preview_availability
from app.services.scheduling_common import SchedulingDomainError
from app.services.web_auth import require_web_session_identity, validate_web_boundary
from app.services.web_portal_auth import require_effective_owner_identity
from app.services.web_schedule import get_web_schedule

router = APIRouter(prefix="/web/api/schedule", tags=["web-schedule"])
SessionDependency = Annotated[Session, Depends(get_db_session)]


def read_identity(request: Request, session: SessionDependency) -> RequestIdentity:
    return require_effective_owner_identity(session, request)


def write_identity(request: Request, session: SessionDependency) -> RequestIdentity:
    return require_web_session_identity(session, request)


ReadIdentity = Annotated[RequestIdentity, Depends(read_identity)]
WriteIdentity = Annotated[RequestIdentity, Depends(write_identity)]


def _translate(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.get("", response_model=WebScheduleResponse)
def schedule(
    session: SessionDependency,
    identity: ReadIdentity,
    date_from: date,
    date_to: date,
) -> WebScheduleResponse:
    try:
        query = WebScheduleRangeQuery(date_from=date_from, date_to=date_to)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_schedule_range"},
        ) from exc
    return get_web_schedule(session, identity, query)


@router.get("/default-work-hours", response_model=MasterPreferencesResponse)
def default_work_hours(
    session: SessionDependency,
    identity: WriteIdentity,
) -> MasterPreferencesResponse:
    return get_master_preferences(session, identity)


@router.put("/default-work-hours", response_model=MasterPreferencesResponse)
def update_default_work_hours(
    body: DefaultWorkHoursUpdateRequest,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentity,
) -> MasterPreferencesResponse:
    validate_web_boundary(request)
    return save_default_work_hours(session, identity, body)


@router.post("/preview", response_model=AvailabilityPreviewResponse)
def schedule_preview(
    body: AvailabilityReplaceRequest,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentity,
) -> AvailabilityPreviewResponse:
    validate_web_boundary(request)
    return preview_availability(session, identity, body)


@router.put("", response_model=AvailabilityReplaceResponse)
def schedule_replace(
    body: AvailabilityReplaceRequest,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentity,
) -> AvailabilityReplaceResponse:
    validate_web_boundary(request)
    try:
        return replace_availability(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc
