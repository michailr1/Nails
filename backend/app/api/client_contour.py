from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import ClientRequestIdentity, require_client_request_identity
from app.db import get_db_session
from app.schemas.client_contour import (
    ClientIdentityLookupResponse,
    ClientIdentityUpsertRequest,
    ClientIdentityUpsertResponse,
    ClientPublicCatalogResponse,
    ClientPublicSlotsResponse,
)
from app.services.client_contour import (
    find_public_slots,
    get_client_identity,
    list_public_catalog,
    upsert_client_identity,
)
from app.services.scheduling_common import SchedulingDomainError

router = APIRouter(prefix="/api/v1/client", tags=["client-contour"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
ClientIdentityDependency = Annotated[
    ClientRequestIdentity,
    Depends(require_client_request_identity),
]


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.get("/catalog", response_model=ClientPublicCatalogResponse)
def public_catalog(
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientPublicCatalogResponse:
    return list_public_catalog(session, identity)


@router.get("/slots", response_model=ClientPublicSlotsResponse)
def public_slots(
    session: SessionDependency,
    identity: ClientIdentityDependency,
    day: date,
    service_name: Annotated[str, Query(min_length=1, max_length=160)],
) -> ClientPublicSlotsResponse:
    try:
        return find_public_slots(session, identity, day, service_name)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get("/identity", response_model=ClientIdentityLookupResponse)
def client_identity_get(
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientIdentityLookupResponse:
    return get_client_identity(session, identity)


@router.put("/identity", response_model=ClientIdentityUpsertResponse)
def client_identity_upsert(
    body: ClientIdentityUpsertRequest,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientIdentityUpsertResponse:
    try:
        return upsert_client_identity(session, identity, body)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
