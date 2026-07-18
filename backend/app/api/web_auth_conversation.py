from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.web_auth_conversation import (
    ConversationalChallengeDecisionRequest,
    ConversationalChallengeDecisionResponse,
    ConversationalChallengeLookupResponse,
)
from app.services.web_auth_conversation import (
    decide_conversational_challenge,
    inspect_conversational_challenge,
)
from app.web_auth_identity import require_web_approval_identity

router = APIRouter(tags=["web-auth"])
SessionDependency = Annotated[Session, Depends(get_db_session)]
ApprovalIdentityDependency = Annotated[
    RequestIdentity | None,
    Depends(require_web_approval_identity),
]


@router.get(
    "/api/v1/web-auth/conversation/challenge",
    response_model=ConversationalChallengeLookupResponse,
)
def get_conversational_challenge(
    session: SessionDependency,
    identity: ApprovalIdentityDependency,
    verification_number: str = Query(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$",
    ),
) -> ConversationalChallengeLookupResponse:
    if identity is None:
        return ConversationalChallengeLookupResponse(
            status="not_found",
            expires_at=None,
            remaining_seconds=0,
        )
    result = inspect_conversational_challenge(
        session,
        identity=identity,
        verification_number=verification_number,
    )
    return ConversationalChallengeLookupResponse(
        status=result.status,
        expires_at=result.expires_at,
        remaining_seconds=result.remaining_seconds,
    )


@router.post(
    "/api/v1/web-auth/conversation/decision",
    response_model=ConversationalChallengeDecisionResponse,
)
def decide_conversational_login(
    body: ConversationalChallengeDecisionRequest,
    session: SessionDependency,
    identity: ApprovalIdentityDependency,
) -> ConversationalChallengeDecisionResponse:
    if identity is None:
        return ConversationalChallengeDecisionResponse(
            status="not_found",
            expires_at=None,
            remaining_seconds=0,
        )
    result = decide_conversational_challenge(
        session,
        identity=identity,
        verification_number=body.verification_number,
        decision=body.decision,
    )
    return ConversationalChallengeDecisionResponse(
        status=result.status,
        expires_at=result.expires_at,
        remaining_seconds=result.remaining_seconds,
    )
