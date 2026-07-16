from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity, require_request_identity
from app.config import get_settings
from app.db import get_db_session
from app.feedback_models import FeedbackEvent, FeedbackKind
from app.models import AuditEvent, UserRole

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
IdentityDependency = Annotated[RequestIdentity, Depends(require_request_identity)]


class FeedbackMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=1000)


class FeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FeedbackKind
    context: list[FeedbackMessage] = Field(min_length=1, max_length=4)


class FeedbackEventResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    actor_user_id: uuid.UUID
    kind: FeedbackKind
    safe_context: list[FeedbackMessage]
    created_at: datetime


class FeedbackCreateResponse(BaseModel):
    saved: bool
    feedback_id: uuid.UUID
    safe_context: list[FeedbackMessage]


class FeedbackListResponse(BaseModel):
    events: list[FeedbackEventResponse]


class FeedbackDeleteResponse(BaseModel):
    deleted: bool


def _require_admin(identity: RequestIdentity) -> None:
    if identity.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_required"},
        )


def _safe_context(messages: list[FeedbackMessage]) -> list[dict[str, str]]:
    return [
        {"role": message.role, "text": message.text.strip()}
        for message in messages[-4:]
    ]


def _purge_expired(session: Session) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().feedback_retention_days)
    session.execute(delete(FeedbackEvent).where(FeedbackEvent.created_at < cutoff))


@router.post("", response_model=FeedbackCreateResponse)
def create_feedback(
    body: FeedbackCreateRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> FeedbackCreateResponse:
    _purge_expired(session)
    safe_context = _safe_context(body.context)
    event = FeedbackEvent(
        owner_user_id=identity.user_id,
        actor_user_id=identity.user_id,
        kind=body.kind,
        safe_context=safe_context,
    )
    session.add(event)
    session.flush()
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="feedback.created",
            object_type="feedback_event",
            object_id=event.id,
            request_id=identity.request_id,
            safe_changes={"kind": body.kind.value},
        )
    )
    session.commit()
    return FeedbackCreateResponse(
        saved=True,
        feedback_id=event.id,
        safe_context=[FeedbackMessage.model_validate(item) for item in safe_context],
    )


@router.get("", response_model=FeedbackListResponse)
def list_feedback(
    session: SessionDependency,
    identity: IdentityDependency,
) -> FeedbackListResponse:
    _require_admin(identity)
    _purge_expired(session)
    events = session.scalars(
        select(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(200)
    ).all()
    session.commit()
    return FeedbackListResponse(
        events=[
            FeedbackEventResponse(
                id=event.id,
                owner_user_id=event.owner_user_id,
                actor_user_id=event.actor_user_id,
                kind=event.kind,
                safe_context=[
                    FeedbackMessage.model_validate(item) for item in event.safe_context
                ],
                created_at=event.created_at,
            )
            for event in events
        ]
    )


@router.delete("/{feedback_id}", response_model=FeedbackDeleteResponse)
def delete_feedback(
    feedback_id: uuid.UUID,
    session: SessionDependency,
    identity: IdentityDependency,
) -> FeedbackDeleteResponse:
    _require_admin(identity)
    _purge_expired(session)
    event = session.get(FeedbackEvent, feedback_id)
    if event is None:
        session.commit()
        return FeedbackDeleteResponse(deleted=False)
    kind = event.kind.value
    owner_user_id = event.owner_user_id
    session.delete(event)
    session.add(
        AuditEvent(
            owner_user_id=owner_user_id,
            actor_user_id=identity.user_id,
            action="feedback.deleted",
            object_type="feedback_event",
            object_id=feedback_id,
            request_id=identity.request_id,
            safe_changes={"kind": kind},
        )
    )
    session.commit()
    return FeedbackDeleteResponse(deleted=True)
