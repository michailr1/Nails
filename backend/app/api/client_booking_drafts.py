from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity, require_client_transport_identity
from app.client_booking_draft_models import ClientBookingDraft
from app.db import get_db_session
from app.schemas.client_booking_drafts import (
    ClientBookingDraftCompositionUpdate,
    ClientBookingDraftCreate,
    ClientBookingDraftNoteUpdate,
    ClientBookingDraftSlotsResponse,
    ClientBookingDraftSlotUpdate,
    ClientBookingDraftSubmitResponse,
    ClientBookingDraftSummary,
)
from app.schemas.client_repeat_last import ClientRepeatLastPreview
from app.services.client_booking_draft_submit import submit_booking_draft_idempotent
from app.services.client_booking_drafts import (
    create_booking_draft,
    draft_slots,
    get_booking_draft,
    select_booking_draft_slot,
    update_booking_draft_composition,
    update_booking_draft_note,
)
from app.services.client_contour import require_client_binding
from app.services.client_repeat_last import (
    create_repeat_last_draft,
    repeat_last_preview,
)
from app.services.scheduling_common import SchedulingDomainError

router = APIRouter(
    prefix="/api/v1/client/booking-drafts",
    tags=["client-booking-drafts"],
)
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


def _binding_context(session, identity, binding_header):
    return require_client_binding(
        session,
        identity,
        binding_id=_uuid(binding_header, "invalid_client_binding_id"),
    )


def _draft_context(
    session: Session,
    identity: ClientTransportIdentity,
    draft_id: uuid.UUID,
):
    draft = session.get(ClientBookingDraft, draft_id)
    if draft is None:
        raise SchedulingDomainError("client_booking_draft_not_found", status_code=404)
    return require_client_binding(
        session,
        identity,
        binding_id=draft.binding_id,
    )


@router.post("", response_model=ClientBookingDraftSummary)
def create_draft(
    body: ClientBookingDraftCreate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSummary:
    try:
        context = _binding_context(session, identity, binding_header)
        return create_booking_draft(session, context, body.service_name)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.get("/repeat-last", response_model=ClientRepeatLastPreview)
def get_repeat_last(
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientRepeatLastPreview:
    try:
        context = _binding_context(session, identity, binding_header)
        return repeat_last_preview(session, context)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.post("/repeat-last", response_model=ClientBookingDraftSummary)
def create_repeat_last(
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientBookingDraftSummary:
    try:
        context = _binding_context(session, identity, binding_header)
        return create_repeat_last_draft(session, context)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.get("/{draft_id}", response_model=ClientBookingDraftSummary)
def get_draft(
    draft_id: uuid.UUID,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientBookingDraftSummary:
    try:
        context = _draft_context(session, identity, draft_id)
        return get_booking_draft(session, context, draft_id)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.put("/{draft_id}/composition", response_model=ClientBookingDraftSummary)
def update_composition(
    draft_id: uuid.UUID,
    body: ClientBookingDraftCompositionUpdate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientBookingDraftSummary:
    try:
        context = _draft_context(session, identity, draft_id)
        return update_booking_draft_composition(
            session,
            context,
            draft_id,
            addon_names=body.addon_names,
            addon_quantities=body.addon_quantities,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.put("/{draft_id}/note", response_model=ClientBookingDraftSummary)
def update_note(
    draft_id: uuid.UUID,
    body: ClientBookingDraftNoteUpdate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientBookingDraftSummary:
    try:
        context = _draft_context(session, identity, draft_id)
        return update_booking_draft_note(
            session,
            context,
            draft_id,
            body.note,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.get("/{draft_id}/slots", response_model=ClientBookingDraftSlotsResponse)
def get_slots(
    draft_id: uuid.UUID,
    day: date,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientBookingDraftSlotsResponse:
    try:
        context = _draft_context(session, identity, draft_id)
        return draft_slots(session, context, draft_id, day)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.put("/{draft_id}/slot", response_model=ClientBookingDraftSummary)
def choose_slot(
    draft_id: uuid.UUID,
    body: ClientBookingDraftSlotUpdate,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientBookingDraftSummary:
    try:
        context = _draft_context(session, identity, draft_id)
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
) -> ClientBookingDraftSubmitResponse:
    try:
        context = _draft_context(session, identity, draft_id)
        request = submit_booking_draft_idempotent(
            session,
            identity,
            context,
            draft_id,
        )
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
