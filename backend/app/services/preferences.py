from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent
from app.models_preferences import MasterPreferences
from app.schemas.preferences import (
    AssistantStyleUpdateRequest,
    DefaultWorkHoursUpdateRequest,
    MasterPreferencesResponse,
    PreferredNameUpdateRequest,
)


def _load_preferences(
    session: Session,
    user_id: uuid.UUID,
    *,
    lock: bool,
) -> MasterPreferences | None:
    statement = select(MasterPreferences).where(MasterPreferences.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _serialize(preferences: MasterPreferences | None) -> MasterPreferencesResponse:
    if preferences is None:
        return MasterPreferencesResponse(
            preferred_name=None,
            assistant_style=None,
            assistant_style_details=None,
            default_work_intervals=None,
            is_complete=False,
        )

    return MasterPreferencesResponse(
        preferred_name=preferences.preferred_name,
        assistant_style=preferences.assistant_style,
        assistant_style_details=preferences.assistant_style_details,
        default_work_intervals=preferences.default_work_intervals,
        is_complete=bool(
            preferences.preferred_name
            and preferences.assistant_style
            and preferences.default_work_intervals is not None
        ),
    )


def _add_audit(
    session: Session,
    identity: RequestIdentity,
    action: str,
    safe_changes: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action=action,
            object_type="master_preferences",
            object_id=identity.user_id,
            request_id=identity.request_id,
            safe_changes=safe_changes,
        )
    )


def get_master_preferences(
    session: Session,
    identity: RequestIdentity,
) -> MasterPreferencesResponse:
    return _serialize(_load_preferences(session, identity.user_id, lock=False))


def save_preferred_name(
    session: Session,
    identity: RequestIdentity,
    body: PreferredNameUpdateRequest,
) -> MasterPreferencesResponse:
    preferences = _load_preferences(session, identity.user_id, lock=True)
    if preferences is None:
        preferences = MasterPreferences(user_id=identity.user_id)
        session.add(preferences)

    if preferences.preferred_name != body.preferred_name:
        preferences.preferred_name = body.preferred_name
        _add_audit(
            session,
            identity,
            "master_preferences.name_saved",
            {"preferred_name_set": True},
        )
        session.commit()

    return _serialize(_load_preferences(session, identity.user_id, lock=False))


def save_assistant_style(
    session: Session,
    identity: RequestIdentity,
    body: AssistantStyleUpdateRequest,
) -> MasterPreferencesResponse:
    preferences = _load_preferences(session, identity.user_id, lock=True)
    if preferences is None:
        preferences = MasterPreferences(user_id=identity.user_id)
        session.add(preferences)

    changed = (
        preferences.assistant_style != body.style
        or preferences.assistant_style_details != body.details
    )
    if changed:
        preferences.assistant_style = body.style
        preferences.assistant_style_details = body.details
        _add_audit(
            session,
            identity,
            "master_preferences.style_saved",
            {
                "assistant_style": body.style,
                "details_set": body.details is not None,
            },
        )
        session.commit()

    return _serialize(_load_preferences(session, identity.user_id, lock=False))


def save_default_work_hours(
    session: Session,
    identity: RequestIdentity,
    body: DefaultWorkHoursUpdateRequest,
) -> MasterPreferencesResponse:
    preferences = _load_preferences(session, identity.user_id, lock=True)
    if preferences is None:
        preferences = MasterPreferences(user_id=identity.user_id)
        session.add(preferences)

    intervals = [item.model_dump(mode="json") for item in body.intervals]
    if preferences.default_work_intervals != intervals:
        preferences.default_work_intervals = intervals
        _add_audit(
            session,
            identity,
            "master_preferences.default_work_hours_saved",
            {
                "uses_default_work_hours": bool(intervals),
                "interval_count": len(intervals),
            },
        )
        session.commit()

    return _serialize(_load_preferences(session, identity.user_id, lock=False))
