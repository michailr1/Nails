from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import RequestIdentity, require_internal_key, require_request_identity
from app.db import get_db_session
from app.schemas.scheduling_digest import (
    FinalizationDigestAckRequest,
    FinalizationDigestAckResponse,
    FinalizationDigestClaimRequest,
    FinalizationDigestClaimResponse,
    FinalizationDigestOwnersResponse,
)
from app.services.scheduling_digest import (
    acknowledge_finalization_digest,
    claim_finalization_digest,
    list_digest_owners,
)

router = APIRouter(
    prefix="/api/v1/scheduling/finalization-digest",
    tags=["scheduling"],
)

SessionDependency = Annotated[Session, Depends(get_db_session)]
IdentityDependency = Annotated[RequestIdentity, Depends(require_request_identity)]
InternalKeyDependency = Annotated[None, Depends(require_internal_key)]


@router.get("/owners", response_model=FinalizationDigestOwnersResponse)
def owners(
    session: SessionDependency,
    _: InternalKeyDependency,
) -> FinalizationDigestOwnersResponse:
    return list_digest_owners(session)


@router.post("/claim", response_model=FinalizationDigestClaimResponse)
def claim(
    body: FinalizationDigestClaimRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> FinalizationDigestClaimResponse:
    return claim_finalization_digest(session, identity, body)


@router.post("/ack", response_model=FinalizationDigestAckResponse)
def ack(
    body: FinalizationDigestAckRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> FinalizationDigestAckResponse:
    return acknowledge_finalization_digest(session, identity, body)
