from __future__ import annotations

import uuid
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity
from app.client_booking_draft_models import ClientBookingDraft
from app.client_models import BookingRequest
from app.services.client_booking_drafts import submit_booking_draft
from app.services.client_contour import ClientBindingContext


def submit_booking_draft_idempotent(
    session: Session,
    identity: ClientTransportIdentity,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
) -> BookingRequest:
    draft = session.scalar(
        select(ClientBookingDraft).where(
            ClientBookingDraft.id == draft_id,
            ClientBookingDraft.owner_user_id == context.owner_user_id,
            ClientBookingDraft.binding_id == context.binding.id,
        )
    )
    if draft is not None and draft.starts_at is not None:
        selected_utc = draft.starts_at.astimezone(UTC)
        idempotency_key = f"client-draft:{draft.id}:{selected_utc:%Y%m%d%H%M}"
        existing = session.scalar(
            select(BookingRequest).where(
                BookingRequest.owner_user_id == context.owner_user_id,
                BookingRequest.binding_id == context.binding.id,
                BookingRequest.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
    return submit_booking_draft(session, identity, context, draft_id)
