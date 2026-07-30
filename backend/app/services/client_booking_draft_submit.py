from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity
from app.client_booking_draft_models import ClientBookingDraft
from app.client_models import BookingRequest
from app.services.client_booking_drafts import (
    _composition,
    _require_draft,
    draft_slots,
)
from app.services.client_booking_requests import create_client_booking_request
from app.services.client_contour import ClientBindingContext
from app.services.scheduling_common import SchedulingDomainError, app_timezone


def _submitted_request(
    session: Session,
    context: ClientBindingContext,
    draft: ClientBookingDraft,
) -> BookingRequest | None:
    if draft.submitted_request_id is not None:
        request = session.get(BookingRequest, draft.submitted_request_id)
        if (
            request is not None
            and request.owner_user_id == context.owner_user_id
            and request.binding_id == context.binding.id
        ):
            return request
    return session.scalar(
        select(BookingRequest).where(
            BookingRequest.owner_user_id == context.owner_user_id,
            BookingRequest.binding_id == context.binding.id,
            BookingRequest.source_draft_id == draft.id,
        )
    )


def _close_draft(
    session: Session,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
    request: BookingRequest,
) -> BookingRequest:
    draft = session.scalar(
        select(ClientBookingDraft)
        .where(
            ClientBookingDraft.id == draft_id,
            ClientBookingDraft.owner_user_id == context.owner_user_id,
            ClientBookingDraft.binding_id == context.binding.id,
        )
        .with_for_update()
    )
    if draft is None:
        raise SchedulingDomainError("client_booking_draft_not_found", status_code=404)
    if draft.submitted_request_id is None:
        draft.submitted_request_id = request.id
        draft.submitted_at = datetime.now(UTC)
        session.commit()
    elif draft.submitted_request_id != request.id:
        raise SchedulingDomainError("client_booking_draft_already_submitted", status_code=409)
    return request


def submit_booking_draft_idempotent(
    session: Session,
    identity: ClientTransportIdentity,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
) -> BookingRequest:
    draft = _require_draft(
        session,
        context,
        draft_id,
        lock=True,
        allow_submitted=True,
    )
    existing = _submitted_request(session, context, draft)
    if existing is not None:
        if draft.submitted_request_id is None:
            return _close_draft(session, context, draft_id, existing)
        return existing

    composition = _composition(session, draft)
    if draft.starts_at is None:
        raise SchedulingDomainError("client_booking_slot_required", status_code=422)
    if draft.starts_at.astimezone(UTC) <= datetime.now(UTC):
        raise SchedulingDomainError("booking_request_start_in_past", status_code=422)

    available = draft_slots(
        session,
        context,
        draft.id,
        draft.starts_at.astimezone(app_timezone()).date(),
    )
    selected_utc = draft.starts_at.astimezone(UTC)
    if not any(slot.astimezone(UTC) == selected_utc for slot in available.starts_at):
        raise SchedulingDomainError("client_booking_slot_stale", status_code=409)

    addon_names = [addon.public_name for addon in composition.addons]
    addon_quantities = {
        addon.public_name.casefold(): composition.quantities[addon.id]
        for addon in composition.addons
        if composition.quantities[addon.id] != 1
    }
    request = create_client_booking_request(
        session,
        identity,
        context,
        service_name=composition.service.public_name,
        addon_names=addon_names,
        addon_quantities=addon_quantities,
        starts_at=draft.starts_at,
        idempotency_key=f"client-draft:{draft.id}",
        source_draft_id=draft.id,
    )
    return _close_draft(session, context, draft_id, request)
