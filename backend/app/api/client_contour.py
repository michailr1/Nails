import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity, require_client_transport_identity
from app.db import get_db_session
from app.schemas.client_contour import (
    ClientContextResponse,
    ClientEntryState,
    ClientPublicCatalogResponse,
    ClientPublicSlotsResponse,
    ClientStartRequest,
)
from app.services.client_context_selection import (
    apply_sticky_context,
    remember_client_binding,
)
from app.services.client_contour import (
    find_public_slots,
    get_client_context,
    list_public_catalog,
    require_client_binding,
    start_client_context,
)
from app.services.scheduling_common import SchedulingDomainError

router = APIRouter(prefix="/api/v1/client", tags=["client-contour"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
ClientIdentityDependency = Annotated[
    ClientTransportIdentity,
    Depends(require_client_transport_identity),
]
BindingHeader = Annotated[str, Header(alias="X-Client-Binding-ID", min_length=1)]


def _translate_domain_error(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


def _binding_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_client_binding_id"},
        ) from exc


def _ready_for_master(master) -> ClientContextResponse:
    return ClientContextResponse(
        state=ClientEntryState.ready,
        message=(
            f"👋 Здравствуйте! Вы записываетесь к **{master.display_name}**.\n"
            "[💅 Прайс] [📅 Записаться] [🗂 Мои записи]"
        ),
        master=master,
    )


@router.post("/start", response_model=ClientContextResponse)
def client_start(
    body: ClientStartRequest,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientContextResponse:
    try:
        response = start_client_context(session, identity, body)
        if response.state == ClientEntryState.ready and response.master is not None:
            remember_client_binding(
                session,
                identity,
                binding_id=response.master.binding_id,
            )
        return response
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get("/context", response_model=ClientContextResponse)
def client_context(
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientContextResponse:
    response = get_client_context(session, identity)
    return apply_sticky_context(session, identity, response)


@router.get("/masters", response_model=ClientContextResponse)
def client_masters(
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientContextResponse:
    return get_client_context(session, identity)


@router.post("/context/select", response_model=ClientContextResponse)
def select_client_context(
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientContextResponse:
    try:
        master = remember_client_binding(
            session,
            identity,
            binding_id=_binding_id(binding_header),
        )
        return _ready_for_master(master)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get("/catalog", response_model=ClientPublicCatalogResponse)
def public_catalog(
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ClientPublicCatalogResponse:
    try:
        context = require_client_binding(
            session,
            identity,
            binding_id=_binding_id(binding_header),
        )
        return list_public_catalog(session, context)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get("/slots", response_model=ClientPublicSlotsResponse)
def public_slots(
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
    day: date,
    service_name: Annotated[str, Query(min_length=1, max_length=160)],
) -> ClientPublicSlotsResponse:
    try:
        context = require_client_binding(
            session,
            identity,
            binding_id=_binding_id(binding_header),
        )
        return find_public_slots(session, context, day, service_name)
    except SchedulingDomainError as exc:
        raise _translate_domain_error(exc) from exc
