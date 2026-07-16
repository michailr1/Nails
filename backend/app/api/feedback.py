from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import RequestIdentity, require_request_identity
from app.db import get_db_session
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackCreateResponse,
    FeedbackDeleteResponse,
    FeedbackEventResponse,
    FeedbackListResponse,
    FeedbackMessage,
)
from app.services.feedback import delete_feedback, list_feedback, save_feedback

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])
SessionDependency = Annotated[Session, Depends(get_db_session)]
IdentityDependency = Annotated[RequestIdentity, Depends(require_request_identity)]


def _event_response(event) -> FeedbackEventResponse:
    return FeedbackEventResponse(
        id=event.id,
        owner_user_id=event.owner_user_id,
        actor_user_id=event.actor_user_id,
        kind=event.kind,
        safe_context=[FeedbackMessage.model_validate(item) for item in event.safe_context],
        created_at=event.created_at,
    )


@router.post("", response_model=FeedbackCreateResponse, status_code=status.HTTP_201_CREATED)
def feedback_create(
    body: FeedbackCreateRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> FeedbackCreateResponse:
    event = save_feedback(session, identity, body)
    return FeedbackCreateResponse(saved=True, event_id=event.id)


@router.get("", response_model=FeedbackListResponse)
def feedback_list(
    session: SessionDependency,
    identity: IdentityDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> FeedbackListResponse:
    events = list_feedback(session, identity, limit)
    return FeedbackListResponse(events=[_event_response(event) for event in events])


@router.delete("/{event_id}", response_model=FeedbackDeleteResponse)
def feedback_delete(
    event_id: uuid.UUID,
    session: SessionDependency,
    identity: IdentityDependency,
) -> FeedbackDeleteResponse:
    return FeedbackDeleteResponse(deleted=delete_feedback(session, identity, event_id))
