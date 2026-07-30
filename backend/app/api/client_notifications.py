from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_client_internal_key
from app.db import get_db_session
from app.schemas.client_notifications import (
    ClientNotificationAckRequest,
    ClientNotificationAckResponse,
    ClientNotificationClaim,
)
from app.services.client_notifications import (
    acknowledge_client_notification,
    claim_client_notification,
)

router = APIRouter(prefix="/api/v1/client/notifications", tags=["client-notifications"])
SessionDependency = Annotated[Session, Depends(get_db_session)]
ClientInternalKeyDependency = Annotated[None, Depends(require_client_internal_key)]


@router.post("/internal/claim", response_model=ClientNotificationClaim)
def claim_notification(
    session: SessionDependency,
    _: ClientInternalKeyDependency,
) -> ClientNotificationClaim:
    return claim_client_notification(session)


@router.post("/internal/ack", response_model=ClientNotificationAckResponse)
def ack_notification(
    body: ClientNotificationAckRequest,
    session: SessionDependency,
    _: ClientInternalKeyDependency,
) -> ClientNotificationAckResponse:
    return acknowledge_client_notification(
        session,
        claim_id=body.claim_id,
        outcome=body.outcome,
        error_code=body.error_code,
    )
