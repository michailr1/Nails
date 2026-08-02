from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus
from app.schemas.client_booking_drafts import ClientBookingDraftSummary
from app.schemas.client_repeat_last import ClientRepeatLastPreview
from app.services.client_booking_drafts import (
    create_booking_draft,
    update_booking_draft_composition,
)
from app.services.client_contour import ClientBindingContext
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_lookup import get_active_addons, get_active_service


@dataclass(frozen=True, slots=True)
class RepeatComposition:
    service_name: str
    addon_names: list[str]
    addon_quantities: dict[str, int]


def _last_booking(
    session: Session,
    context: ClientBindingContext,
) -> Booking | None:
    client_id = context.binding.client_id
    if client_id is None:
        return None
    return session.scalar(
        select(Booking)
        .where(
            Booking.owner_user_id == context.owner_user_id,
            Booking.client_id == client_id,
            Booking.starts_at < datetime.now(UTC),
            Booking.status.in_((BookingStatus.scheduled, BookingStatus.completed)),
        )
        .order_by(Booking.starts_at.desc(), Booking.id.desc())
        .limit(1)
    )


def _snapshot_composition(booking: Booking) -> RepeatComposition | None:
    service_name: str | None = None
    addon_names: list[str] = []
    addon_quantities: dict[str, int] = {}
    for raw_item in booking.catalog_items_snapshot:
        if not isinstance(raw_item, dict):
            continue
        name = raw_item.get("public_name")
        kind = raw_item.get("kind")
        if not isinstance(name, str) or not name.strip():
            continue
        canonical = " ".join(name.split())
        if kind == "base" and service_name is None:
            service_name = canonical
        elif kind == "addon":
            addon_names.append(canonical)
            quantity = raw_item.get("quantity", 1)
            if isinstance(quantity, int) and quantity > 1:
                addon_quantities[canonical.casefold()] = quantity
    if service_name is None:
        return None
    return RepeatComposition(
        service_name=service_name,
        addon_names=addon_names,
        addon_quantities=addon_quantities,
    )


def _current_composition(
    session: Session,
    context: ClientBindingContext,
) -> RepeatComposition | None:
    booking = _last_booking(session, context)
    if booking is None:
        return None
    snapshot = _snapshot_composition(booking)
    if snapshot is None:
        return None
    try:
        service = get_active_service(
            session,
            context.owner_user_id,
            snapshot.service_name,
        )
        if service.kind != "base":
            return None
        addons = get_active_addons(
            session,
            context.owner_user_id,
            snapshot.addon_names,
        )
    except SchedulingDomainError:
        return None
    canonical_quantities = {
        addon.public_name.casefold(): snapshot.addon_quantities.get(
            addon.public_name.casefold(),
            1,
        )
        for addon in addons
        if snapshot.addon_quantities.get(addon.public_name.casefold(), 1) != 1
    }
    return RepeatComposition(
        service_name=service.public_name,
        addon_names=[addon.public_name for addon in addons],
        addon_quantities=canonical_quantities,
    )


def repeat_last_preview(
    session: Session,
    context: ClientBindingContext,
) -> ClientRepeatLastPreview:
    composition = _current_composition(session, context)
    if composition is None:
        return ClientRepeatLastPreview(available=False)
    return ClientRepeatLastPreview(
        available=True,
        service_name=composition.service_name,
        addon_names=composition.addon_names,
        addon_quantities=composition.addon_quantities,
    )


def create_repeat_last_draft(
    session: Session,
    context: ClientBindingContext,
) -> ClientBookingDraftSummary:
    composition = _current_composition(session, context)
    if composition is None:
        raise SchedulingDomainError("client_repeat_last_unavailable", status_code=404)
    draft = create_booking_draft(session, context, composition.service_name)
    if not composition.addon_names:
        return draft
    return update_booking_draft_composition(
        session,
        context,
        draft.draft_id,
        addon_names=composition.addon_names,
        addon_quantities=composition.addon_quantities,
    )
