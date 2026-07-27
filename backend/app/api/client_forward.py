import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    ClientTransportIdentity,
    require_client_transport_identity,
    require_internal_key,
)
from app.db import get_db_session
from app.schemas.client_contour import (
    ClientContactForwardAckRequest,
    ClientContactForwardAckResponse,
    ClientContactForwardClaim,
    ClientContactForwardRequest,
    ClientContactForwardResponse,
)
from app.services.client_contact_forward import (
    acknowledge_client_contact_forward,
    claim_client_contact_forward,
    enqueue_client_contact_forward,
)
from app.services.scheduling_common import SchedulingDomainError

router = APIRouter(prefix="/api/v1/client", tags=["client-contact-forward"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
ClientIdentityDependency = Annotated[
    ClientTransportIdentity,
    Depends(require_client_transport_identity),
]
BindingHeader = Annotated[str, Header(alias="X-Client-Binding-ID", min_length=1)]
InternalKeyDependency = Annotated[None, Depends(require_internal_key)]


def _binding_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_client_binding_id"},
        ) from exc


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.post("/contact-forward", response_model=ClientContactForwardResponse)
def create_contact_forward(
    body: ClientContactForwardRequest,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientContactForwardResponse:
    try:
        return enqueue_client_contact_forward(
            session,
            identity,
            binding_id=_binding_id(binding_header),
            message_text=body.message_text,
        )
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post("/contact-forward/internal/claim", response_model=ClientContactForwardClaim)
def claim_contact_forward(
    session: SessionDependency,
    _: InternalKeyDependency,
) -> ClientContactForwardClaim:
    return claim_client_contact_forward(session)


@router.post(
    "/contact-forward/internal/ack",
    response_model=ClientContactForwardAckResponse,
)
def ack_contact_forward(
    body: ClientContactForwardAckRequest,
    session: SessionDependency,
    _: InternalKeyDependency,
) -> ClientContactForwardAckResponse:
    return acknowledge_client_contact_forward(
        session,
        claim_id=body.claim_id,
        sent=body.sent,
    )
