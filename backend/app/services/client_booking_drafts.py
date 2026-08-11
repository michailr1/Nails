from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity
from app.client_booking_draft_models import ClientBookingDraft
from app.models import Booking, BookingStatus, Service
from app.schemas.client_booking_drafts import (
    ClientBookingAddonOption,
    ClientBookingDraftSlotsResponse,
    ClientBookingDraftSummary,
)
from app.services.catalog_inclusions import included_addon_ids, per_unit_time_addon_ids
from app.services.client_booking_requests import create_client_booking_request
from app.services.client_contour import ClientBindingContext
from app.services.scheduling_bookings import _catalog_price_semantics
from app.services.scheduling_common import (
    SLOT_STEP_MINUTES,
    SchedulingDomainError,
    availability_for_day,
    calculate_reservation,
    ceil_to_step,
    day_bounds,
    overlaps,
    suggestion_windows_for_day,
)
from app.services.scheduling_lookup import get_active_addons, get_active_service
from app.timezones import owner_timezone

_DRAFT_TTL = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class _Composition:
    service: Service
    addons: list[Service]
    quantities: dict[uuid.UUID, int]
    included_ids: set[uuid.UUID]
    per_unit_ids: set[uuid.UUID]
    duration_minutes: int


def _touch(draft: ClientBookingDraft) -> None:
    draft.expires_at = datetime.now(UTC) + _DRAFT_TTL


def _require_draft(
    session: Session,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
    *,
    lock: bool = False,
    allow_submitted: bool = False,
) -> ClientBookingDraft:
    statement = select(ClientBookingDraft).where(
        ClientBookingDraft.id == draft_id,
        ClientBookingDraft.owner_user_id == context.owner_user_id,
        ClientBookingDraft.binding_id == context.binding.id,
    )
    if lock:
        statement = statement.with_for_update()
    draft = session.scalar(statement)
    if draft is None:
        raise SchedulingDomainError("client_booking_draft_not_found", status_code=404)
    if draft.submitted_request_id is not None and not allow_submitted:
        raise SchedulingDomainError("client_booking_draft_submitted", status_code=409)
    if draft.expires_at <= datetime.now(UTC):
        raise SchedulingDomainError("client_booking_draft_expired", status_code=409)
    return draft


def _composition(session: Session, draft: ClientBookingDraft) -> _Composition:
    service = get_active_service(session, draft.owner_user_id, draft.service_name)
    if service.kind != "base":
        raise SchedulingDomainError("base_service_not_found", status_code=404)
    addons = get_active_addons(session, draft.owner_user_id, list(draft.addon_names))
    quantities = {
        addon.id: int(draft.addon_quantities.get(addon.public_name.casefold(), 1))
        for addon in addons
    }
    addon_ids = [addon.id for addon in addons]
    included_ids = included_addon_ids(
        session,
        draft.owner_user_id,
        service.id,
        addon_ids,
    )
    per_unit_ids = per_unit_time_addon_ids(session, draft.owner_user_id, addon_ids)
    invalid_quantity = next(
        (
            addon.public_name
            for addon in addons
            if quantities[addon.id] != 1
            and addon.price_type != "per_unit"
            and addon.id not in per_unit_ids
        ),
        None,
    )
    if invalid_quantity is not None:
        raise SchedulingDomainError(
            "addon_quantity_not_supported",
            status_code=422,
            details={"addon_name": invalid_quantity},
        )
    duration = service.duration_minutes + sum(
        0
        if addon.id in included_ids
        else addon.extra_minutes * (quantities[addon.id] if addon.id in per_unit_ids else 1)
        for addon in addons
    )
    return _Composition(
        service=service,
        addons=addons,
        quantities=quantities,
        included_ids=included_ids,
        per_unit_ids=per_unit_ids,
        duration_minutes=duration,
    )


def _addon_options(
    session: Session,
    owner_user_id: uuid.UUID,
    service: Service,
) -> list[ClientBookingAddonOption]:
    addons = list(
        session.scalars(
            select(Service)
            .where(
                Service.owner_user_id == owner_user_id,
                Service.is_active.is_(True),
                Service.kind == "addon",
            )
            .order_by(
                func.coalesce(Service.category, ""),
                Service.sort_order,
                Service.public_name,
            )
        ).all()
    )
    addon_ids = [addon.id for addon in addons]
    included_ids = included_addon_ids(session, owner_user_id, service.id, addon_ids)
    per_unit_ids = per_unit_time_addon_ids(session, owner_user_id, addon_ids)
    return [
        ClientBookingAddonOption(
            public_name=addon.public_name,
            price_type=addon.price_type,
            price_amount=(
                addon.price_amount if addon.price_type in {"fixed", "per_unit"} else None
            ),
            price_min_amount=addon.price_min_amount,
            price_max_amount=addon.price_max_amount,
            price_unit=addon.price_unit,
            currency=addon.currency,
            extra_minutes=addon.extra_minutes,
            included_in_base=addon.id in included_ids,
            quantity_supported=(addon.price_type == "per_unit" or addon.id in per_unit_ids),
            time_per_unit=addon.id in per_unit_ids,
        )
        for addon in addons
    ]


def draft_summary(
    session: Session,
    context: ClientBindingContext,
    draft: ClientBookingDraft,
) -> ClientBookingDraftSummary:
    composition = _composition(session, draft)
    semantics = _catalog_price_semantics(
        [composition.service, *composition.addons],
        composition.quantities,
    )
    return ClientBookingDraftSummary(
        draft_id=draft.id,
        master=context.master,
        service_name=composition.service.public_name,
        addon_names=[addon.public_name for addon in composition.addons],
        addon_quantities={
            addon.public_name.casefold(): composition.quantities[addon.id]
            for addon in composition.addons
            if composition.quantities[addon.id] != 1
        },
        note=draft.note,
        starts_at=draft.starts_at,
        duration_minutes=composition.duration_minutes,
        buffer_before_minutes=composition.service.buffer_before_minutes,
        buffer_after_minutes=composition.service.buffer_after_minutes,
        price_type=semantics.price_type,
        price_amount=(
            semantics.legacy_amount
            if semantics.price_type in {"fixed", "per_unit"}
            else None
        ),
        price_min_amount=semantics.price_min,
        price_max_amount=semantics.price_max,
        price_unit=semantics.price_unit,
        currency=composition.service.currency,
        addons=_addon_options(
            session,
            context.owner_user_id,
            composition.service,
        ),
        expires_at=draft.expires_at,
    )


def create_booking_draft(
    session: Session,
    context: ClientBindingContext,
    service_name: str,
) -> ClientBookingDraftSummary:
    service = get_active_service(session, context.owner_user_id, service_name)
    if service.kind != "base":
        raise SchedulingDomainError("base_service_not_found", status_code=404)
    now = datetime.now(UTC)
    draft = ClientBookingDraft(
        owner_user_id=context.owner_user_id,
        binding_id=context.binding.id,
        service_name=service.public_name,
        addon_names=[],
        addon_quantities={},
        note=None,
        starts_at=None,
        expires_at=now + _DRAFT_TTL,
    )
    session.add(draft)
    session.flush()
    result = draft_summary(session, context, draft)
    session.commit()
    return result


def get_booking_draft(
    session: Session,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
) -> ClientBookingDraftSummary:
    draft = _require_draft(session, context, draft_id, allow_submitted=True)
    return draft_summary(session, context, draft)


def update_booking_draft_composition(
    session: Session,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
    *,
    addon_names: list[str],
    addon_quantities: dict[str, int],
) -> ClientBookingDraftSummary:
    draft = _require_draft(session, context, draft_id, lock=True)
    addons = get_active_addons(session, context.owner_user_id, addon_names)
    canonical_names = [addon.public_name for addon in addons]
    quantities: dict[str, int] = {}
    for addon in addons:
        quantity = int(addon_quantities.get(addon.public_name.casefold(), 1))
        if quantity != 1:
            quantities[addon.public_name.casefold()] = quantity
    draft.addon_names = canonical_names
    draft.addon_quantities = quantities
    draft.starts_at = None
    _touch(draft)
    result = draft_summary(session, context, draft)
    session.commit()
    return result


def update_booking_draft_note(
    session: Session,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
    note: str | None,
) -> ClientBookingDraftSummary:
    draft = _require_draft(session, context, draft_id, lock=True)
    draft.note = note
    _touch(draft)
    result = draft_summary(session, context, draft)
    session.commit()
    return result


def _busy_intervals(
    session: Session,
    owner_user_id: uuid.UUID,
    day: date,
) -> list[tuple[datetime, datetime]]:
    timezone = owner_timezone(session, owner_user_id)
    start_at, end_at = day_bounds(day, timezone)
    rows = session.scalars(
        select(Booking).where(
            Booking.owner_user_id == owner_user_id,
            Booking.status == BookingStatus.scheduled,
            Booking.reserved_starts_at < end_at,
            Booking.reserved_ends_at > start_at,
        )
    ).all()
    return [(row.reserved_starts_at, row.reserved_ends_at) for row in rows]


def draft_slots(
    session: Session,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
    day: date,
) -> ClientBookingDraftSlotsResponse:
    draft = _require_draft(session, context, draft_id, allow_submitted=True)
    composition = _composition(session, draft)
    timezone = owner_timezone(session, context.owner_user_id)
    availability = availability_for_day(session, context.owner_user_id, day)
    windows, is_day_off = suggestion_windows_for_day(
        session,
        context.owner_user_id,
        day,
    )
    busy = _busy_intervals(session, context.owner_user_id, day)
    starts: set[datetime] = set()
    for start_time, end_time in windows:
        interval_start = datetime.combine(day, start_time, tzinfo=timezone)
        interval_end = datetime.combine(day, end_time, tzinfo=timezone)
        candidate = ceil_to_step(
            interval_start + timedelta(minutes=composition.service.buffer_before_minutes),
            SLOT_STEP_MINUTES,
        )
        last_start = interval_end - timedelta(
            minutes=composition.duration_minutes
            + composition.service.buffer_after_minutes
        )
        while candidate <= last_start:
            reservation = calculate_reservation(
                composition.service,
                candidate,
                duration_minutes=composition.duration_minutes,
            )
            if not any(
                overlaps(
                    reservation.reserved_starts_at,
                    reservation.reserved_ends_at,
                    busy_start,
                    busy_end,
                )
                for busy_start, busy_end in busy
            ):
                starts.add(candidate)
            candidate += timedelta(minutes=SLOT_STEP_MINUTES)
    return ClientBookingDraftSlotsResponse(
        draft=draft_summary(session, context, draft),
        day=day,
        timezone=str(timezone),
        availability_known=bool(availability),
        is_working=not is_day_off,
        step_minutes=SLOT_STEP_MINUTES,
        starts_at=sorted(starts),
    )


def select_booking_draft_slot(
    session: Session,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
    starts_at: datetime,
) -> ClientBookingDraftSummary:
    draft = _require_draft(session, context, draft_id, lock=True)
    timezone = owner_timezone(session, context.owner_user_id)
    available = draft_slots(
        session,
        context,
        draft.id,
        starts_at.astimezone(timezone).date(),
    )
    requested_utc = starts_at.astimezone(UTC)
    current = next(
        (slot for slot in available.starts_at if slot.astimezone(UTC) == requested_utc),
        None,
    )
    if current is None:
        raise SchedulingDomainError("client_booking_slot_stale", status_code=409)
    draft.starts_at = current
    _touch(draft)
    result = draft_summary(session, context, draft)
    session.commit()
    return result


def submit_booking_draft(
    session: Session,
    identity: ClientTransportIdentity,
    context: ClientBindingContext,
    draft_id: uuid.UUID,
):
    draft = _require_draft(session, context, draft_id, lock=True)
    composition = _composition(session, draft)
    if draft.starts_at is None:
        raise SchedulingDomainError("client_booking_slot_required", status_code=422)
    if draft.starts_at.astimezone(UTC) <= datetime.now(UTC):
        raise SchedulingDomainError("booking_request_start_in_past", status_code=422)
    timezone = owner_timezone(session, context.owner_user_id)
    available = draft_slots(
        session,
        context,
        draft.id,
        draft.starts_at.astimezone(timezone).date(),
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
    return create_client_booking_request(
        session,
        identity,
        context,
        service_name=composition.service.public_name,
        addon_names=addon_names,
        addon_quantities=addon_quantities,
        note=draft.note,
        starts_at=draft.starts_at,
        idempotency_key=f"client-draft:{draft.id}:{selected_utc:%Y%m%d%H%M}",
    )
