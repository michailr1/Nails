from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity, require_client_transport_identity
from app.db import get_db_session
from app.schemas.client_booking_drafts import (
    ClientBookingDraftCompositionUpdate,
    ClientBookingDraftCreate,
    ClientBookingDraftSlotUpdate,
    ClientBookingDraftSlotsResponse,
    ClientBookingDraftSubmitResponse,
    ClientBookingDraftSummary,
)
from app.services.client_booking_drafts import (
    create_booking_draft,
    draft_slots,
    get_booking_draft,
    select_booking_draft_slot,
    submit_booking_draft,
    update_booking_draft_composition,
)
from app.services.client_contour import require_client_binding
from app.services.scheduling_common import SchedulingDomainError

router = APIRouter(prefix="/api/v1/client/booking-drafts", tags=["client-booking-drafts"])
SessionDependency = Annotated[Session, Depends(get_db_session)]
ClientIdentityDependency = Annotated[
    ClientTransportIdentity,
    Depends(require_client_transport_identity),
]
BindingHeader = Annotated[str, Header(alias="X-Client-Binding-ID", min_length=1)]


def _uuid(value: str, code: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": code}) from exc


def _translate(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


def _context(session, identity, binding_header):
    return require_client_binding(
        session,
        identity,
        binding_id=_uuid(binding_header, "invalid_client_binding_id"),
    )


@router.post("", response_model=ClientBookingDraftSummary)
def create_draft(
    body: ClientBookingDraftCreate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSummary:
    try:
        context = _context(session, identity, binding_header)
        return create_booking_draft(session, context, body.service_name)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.get("/{draft_id}", response_model=ClientBookingDraftSummary)
def get_draft(
    draft_id: uuid.UUID,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSummary:
    try:
        context = _context(session, identity, binding_header)
        return get_booking_draft(session, context, draft_id)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.put("/{draft_id}/composition", response_model=ClientBookingDraftSummary)
def update_composition(
    draft_id: uuid.UUID,
    body: ClientBookingDraftCompositionUpdate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSummary:
    try:
        context = _context(session, identity, binding_header)
        return update_booking_draft_composition(
            session,
            context,
            draft_id,
            addon_names=body.addon_names,
            addon_quantities=body.addon_quantities,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.get("/{draft_id}/slots", response_model=ClientBookingDraftSlotsResponse)
def get_slots(
    draft_id: uuid.UUID,
    day: date,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSlotsResponse:
    try:
        context = _context(session, identity, binding_header)
        return draft_slots(session, context, draft_id, day)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.put("/{draft_id}/slot", response_model=ClientBookingDraftSummary)
def choose_slot(
    draft_id: uuid.UUID,
    body: ClientBookingDraftSlotUpdate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSummary:
    try:
        context = _context(session, identity, binding_header)
        return select_booking_draft_slot(
            session,
            context,
            draft_id,
            body.starts_at,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.post("/{draft_id}/submit", response_model=ClientBookingDraftSubmitResponse)
def submit_draft(
    draft_id: uuid.UUID,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSubmitResponse:
    try:
        context = _context(session, identity, binding_header)
        request = submit_booking_draft(session, identity, context, draft_id)
        return ClientBookingDraftSubmitResponse(
            request_id=request.id,
            status=request.status,
            service_name=request.service_name,
            addon_names=list(request.addon_names),
            addon_quantities=dict(request.addon_quantities),
            starts_at=request.starts_at,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc
