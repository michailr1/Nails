from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import RequestIdentity
from app.models import (
    AuditEvent,
    OnboardingDraft,
    OnboardingSection,
    OnboardingState,
    OnboardingStatus,
)
from app.schemas.onboarding import (
    BookingsPayload,
    BuffersPayload,
    DraftResponse,
    OnboardingStateResponse,
    SchedulePayload,
    ServicesPayload,
)

SECTION_ORDER = (
    OnboardingSection.schedule,
    OnboardingSection.services,
    OnboardingSection.buffers,
    OnboardingSection.bookings,
)
SECTION_MODELS: dict[OnboardingSection, type[BaseModel]] = {
    OnboardingSection.schedule: SchedulePayload,
    OnboardingSection.services: ServicesPayload,
    OnboardingSection.buffers: BuffersPayload,
    OnboardingSection.bookings: BookingsPayload,
}


class OnboardingDomainError(Exception):
    def __init__(self, code: str, status_code: int = 409, details: Any | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.details = details


def validate_payload(section: OnboardingSection, payload: dict[str, Any]) -> dict[str, Any]:
    model = SECTION_MODELS[section]
    try:
        parsed = model.model_validate(payload)
    except ValidationError as exc:
        raise OnboardingDomainError(
            "invalid_onboarding_payload",
            status_code=422,
            details=exc.errors(include_url=False, include_input=False),
        ) from exc
    return parsed.model_dump(mode="json")


def _load_state(
    session: Session,
    user_id: uuid.UUID,
    *,
    lock: bool,
) -> OnboardingState | None:
    statement = (
        select(OnboardingState)
        .options(selectinload(OnboardingState.drafts))
        .where(OnboardingState.user_id == user_id)
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _require_state(session: Session, identity: RequestIdentity, *, lock: bool) -> OnboardingState:
    state = _load_state(session, identity.user_id, lock=lock)
    if state is None:
        raise OnboardingDomainError("onboarding_not_started", status_code=404)
    return state


def _draft_map(state: OnboardingState) -> dict[OnboardingSection, OnboardingDraft]:
    return {draft.section: draft for draft in state.drafts}


def _first_unconfirmed_section(state: OnboardingState) -> OnboardingSection | None:
    drafts = _draft_map(state)
    for section in SECTION_ORDER:
        draft = drafts.get(section)
        if draft is None or not draft.is_confirmed:
            return section
    return None


def _sync_current_step(state: OnboardingState) -> None:
    next_section = _first_unconfirmed_section(state)
    state.current_step = next_section.value if next_section is not None else None


def _add_audit(
    session: Session,
    identity: RequestIdentity,
    state: OnboardingState,
    action: str,
    safe_changes: dict[str, Any],
) -> None:
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action=action,
            object_type="onboarding_state",
            object_id=state.id,
            request_id=identity.request_id,
            safe_changes=safe_changes,
        )
    )


def _serialize(state: OnboardingState) -> OnboardingStateResponse:
    drafts = _draft_map(state)
    sections = []
    for section in SECTION_ORDER:
        draft = drafts.get(section)
        if draft is None:
            continue
        confirmed_current = (
            draft.is_confirmed
            and draft.confirmed_revision is not None
            and draft.confirmed_revision == draft.revision
        )
        sections.append(
            DraftResponse(
                section=section,
                draft_payload=draft.payload,
                confirmed_payload=draft.confirmed_payload,
                effective_payload=draft.confirmed_payload,
                revision=draft.revision,
                confirmed_revision=draft.confirmed_revision,
                is_current_revision_confirmed=confirmed_current,
                confirmed_at=draft.confirmed_at,
                updated_at=draft.updated_at,
            )
        )

    return OnboardingStateResponse(
        status=state.status,
        current_step=OnboardingSection(state.current_step) if state.current_step else None,
        started_at=state.started_at,
        completed_at=state.completed_at,
        sections=sections,
    )


def start_onboarding(session: Session, identity: RequestIdentity) -> OnboardingStateResponse:
    state = _load_state(session, identity.user_id, lock=True)
    now = datetime.now(UTC)

    if state is None:
        state = OnboardingState(
            user_id=identity.user_id,
            status=OnboardingStatus.in_progress,
            current_step=OnboardingSection.schedule.value,
            started_at=now,
        )
        session.add(state)
        session.flush()
        _add_audit(
            session,
            identity,
            state,
            "onboarding.started",
            {"status": OnboardingStatus.in_progress.value},
        )
        session.commit()
        session.refresh(state)
        return _serialize(_require_state(session, identity, lock=False))

    if state.status == OnboardingStatus.in_progress:
        return _serialize(state)
    if state.status == OnboardingStatus.paused:
        raise OnboardingDomainError("onboarding_paused_use_resume")
    if state.status == OnboardingStatus.completed:
        raise OnboardingDomainError("onboarding_already_completed")

    state.status = OnboardingStatus.in_progress
    state.started_at = state.started_at or now
    _sync_current_step(state)
    _add_audit(
        session,
        identity,
        state,
        "onboarding.started",
        {"status": OnboardingStatus.in_progress.value},
    )
    session.commit()
    return _serialize(_require_state(session, identity, lock=False))


def get_onboarding_state(session: Session, identity: RequestIdentity) -> OnboardingStateResponse:
    return _serialize(_require_state(session, identity, lock=False))


def save_draft(
    session: Session,
    identity: RequestIdentity,
    section: OnboardingSection,
    payload: dict[str, Any],
) -> OnboardingStateResponse:
    canonical = validate_payload(section, payload)
    state = _require_state(session, identity, lock=True)
    if state.status != OnboardingStatus.in_progress:
        raise OnboardingDomainError("onboarding_not_in_progress")

    drafts = _draft_map(state)
    draft = drafts.get(section)
    if draft is None:
        draft = OnboardingDraft(
            section=section,
            payload=canonical,
            revision=1,
            is_confirmed=False,
        )
        state.drafts.append(draft)
        changed = True
    elif draft.payload == canonical:
        changed = False
    else:
        draft.payload = canonical
        draft.revision += 1
        draft.is_confirmed = False
        changed = True

    if changed:
        _sync_current_step(state)
        _add_audit(
            session,
            identity,
            state,
            "onboarding.draft_saved",
            {
                "section": section.value,
                "revision": draft.revision,
                "has_previous_confirmation": draft.confirmed_payload is not None,
            },
        )
        session.commit()

    return _serialize(_require_state(session, identity, lock=False))


def _require_prior_sections_confirmed(
    state: OnboardingState,
    section: OnboardingSection,
) -> None:
    drafts = _draft_map(state)
    section_index = SECTION_ORDER.index(section)
    missing = [
        candidate.value
        for candidate in SECTION_ORDER[:section_index]
        if candidate not in drafts or not drafts[candidate].is_confirmed
    ]
    if missing:
        raise OnboardingDomainError("prior_sections_not_confirmed", details={"sections": missing})


def _validate_confirmation(state: OnboardingState, draft: OnboardingDraft) -> None:
    if draft.section == OnboardingSection.schedule:
        weekdays = {day["weekday"] for day in draft.payload["days"]}
        if weekdays != set(range(7)):
            raise OnboardingDomainError(
                "schedule_requires_all_weekdays",
                details={"missing_weekdays": sorted(set(range(7)) - weekdays)},
            )

    drafts = _draft_map(state)
    services = drafts.get(OnboardingSection.services)
    if draft.section in {OnboardingSection.buffers, OnboardingSection.bookings}:
        if services is None or services.confirmed_payload is None or not services.is_confirmed:
            raise OnboardingDomainError("services_not_confirmed")
        names = {
            item["public_name"].casefold()
            for item in services.confirmed_payload.get("services", [])
        }
        key = "buffers" if draft.section == OnboardingSection.buffers else "bookings"
        referenced = {
            item["service_name"].casefold()
            for item in draft.payload.get(key, [])
        }
        unknown = sorted(referenced - names)
        if unknown:
            raise OnboardingDomainError(
                "unknown_service_reference",
                details={"service_names": unknown},
            )


def _invalidate_downstream(
    state: OnboardingState,
    section: OnboardingSection,
) -> list[str]:
    drafts = _draft_map(state)
    invalidated = []
    section_index = SECTION_ORDER.index(section)
    for candidate in SECTION_ORDER[section_index + 1 :]:
        downstream = drafts.get(candidate)
        if downstream is None or downstream.confirmed_payload is None:
            continue
        downstream.is_confirmed = False
        downstream.confirmed_payload = None
        downstream.confirmed_revision = None
        downstream.confirmed_at = None
        invalidated.append(candidate.value)
    return invalidated


def confirm_section(
    session: Session,
    identity: RequestIdentity,
    section: OnboardingSection,
) -> OnboardingStateResponse:
    state = _require_state(session, identity, lock=True)
    if state.status != OnboardingStatus.in_progress:
        raise OnboardingDomainError("onboarding_not_in_progress")

    drafts = _draft_map(state)
    draft = drafts.get(section)
    if draft is None:
        raise OnboardingDomainError("section_draft_missing", status_code=404)

    if draft.is_confirmed and draft.confirmed_revision == draft.revision:
        return _serialize(state)

    _require_prior_sections_confirmed(state, section)
    _validate_confirmation(state, draft)

    draft.confirmed_payload = draft.payload
    draft.confirmed_revision = draft.revision
    draft.is_confirmed = True
    draft.confirmed_at = datetime.now(UTC)
    invalidated = _invalidate_downstream(state, section)
    _sync_current_step(state)

    _add_audit(
        session,
        identity,
        state,
        "onboarding.section_confirmed",
        {
            "section": section.value,
            "revision": draft.revision,
            "invalidated_sections": invalidated,
        },
    )
    session.commit()
    return _serialize(_require_state(session, identity, lock=False))


def pause_onboarding(session: Session, identity: RequestIdentity) -> OnboardingStateResponse:
    state = _require_state(session, identity, lock=True)
    if state.status == OnboardingStatus.paused:
        return _serialize(state)
    if state.status != OnboardingStatus.in_progress:
        raise OnboardingDomainError("onboarding_not_in_progress")

    state.status = OnboardingStatus.paused
    _add_audit(
        session,
        identity,
        state,
        "onboarding.paused",
        {"status": OnboardingStatus.paused.value},
    )
    session.commit()
    return _serialize(_require_state(session, identity, lock=False))


def resume_onboarding(session: Session, identity: RequestIdentity) -> OnboardingStateResponse:
    state = _require_state(session, identity, lock=True)
    if state.status == OnboardingStatus.in_progress:
        return _serialize(state)
    if state.status == OnboardingStatus.completed:
        raise OnboardingDomainError("onboarding_already_completed")

    state.status = OnboardingStatus.in_progress
    state.started_at = state.started_at or datetime.now(UTC)
    _sync_current_step(state)
    _add_audit(
        session,
        identity,
        state,
        "onboarding.resumed",
        {"status": OnboardingStatus.in_progress.value},
    )
    session.commit()
    return _serialize(_require_state(session, identity, lock=False))


def complete_onboarding(session: Session, identity: RequestIdentity) -> OnboardingStateResponse:
    state = _require_state(session, identity, lock=True)
    if state.status == OnboardingStatus.completed:
        return _serialize(state)
    if state.status != OnboardingStatus.in_progress:
        raise OnboardingDomainError("onboarding_not_in_progress")

    drafts = _draft_map(state)
    missing = [
        section.value
        for section in SECTION_ORDER
        if section not in drafts or not drafts[section].is_confirmed
    ]
    if missing:
        raise OnboardingDomainError(
            "onboarding_sections_not_confirmed",
            details={"sections": missing},
        )

    state.status = OnboardingStatus.completed
    state.current_step = None
    state.completed_at = datetime.now(UTC)
    _add_audit(
        session,
        identity,
        state,
        "onboarding.completed",
        {"status": OnboardingStatus.completed.value},
    )
    session.commit()
    return _serialize(_require_state(session, identity, lock=False))
