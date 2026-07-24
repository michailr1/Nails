from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.web_admin import (
    AdminMasterCreateRequest,
    AdminMasterCreateResponse,
    AdminMasterListResponse,
    AdminMasterSelectRequest,
    AdminMasterSelectResponse,
)
from app.services.web_admin import (
    AdminDomainError,
    create_master,
    list_masters,
    master_card,
)
from app.services.web_auth import validate_web_boundary
from app.services.web_portal_auth import (
    PortalSessionContext,
    require_portal_session_context,
    require_portal_session_identity,
    select_master_scope,
)

router = APIRouter(prefix="/web/api/admin", tags=["web-admin"])
SessionDependency = Annotated[Session, Depends(get_db_session)]


def require_web_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_portal_session_identity(session, request)


def require_web_context(
    request: Request,
    session: SessionDependency,
) -> PortalSessionContext:
    return require_portal_session_context(session, request)


IdentityDependency = Annotated[RequestIdentity, Depends(require_web_identity)]
ContextDependency = Annotated[PortalSessionContext, Depends(require_web_context)]


def _translate(exc: AdminDomainError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code})


@router.get("/masters", response_model=AdminMasterListResponse)
def masters(
    session: SessionDependency,
    identity: IdentityDependency,
) -> AdminMasterListResponse:
    try:
        users = list_masters(session, identity)
    except AdminDomainError as exc:
        raise _translate(exc) from exc
    return AdminMasterListResponse(masters=[master_card(user) for user in users])


@router.post("/masters", response_model=AdminMasterCreateResponse)
def master_create(
    body: AdminMasterCreateRequest,
    request: Request,
    session: SessionDependency,
    identity: IdentityDependency,
) -> AdminMasterCreateResponse:
    validate_web_boundary(request)
    try:
        result = create_master(
            session,
            identity,
            telegram_user_id=body.telegram_user_id,
        )
    except AdminDomainError as exc:
        raise _translate(exc) from exc
    return AdminMasterCreateResponse(
        master=master_card(result.master),
        created=result.created,
    )


@router.post("/select-master", response_model=AdminMasterSelectResponse)
def master_select(
    body: AdminMasterSelectRequest,
    request: Request,
    session: SessionDependency,
    context: ContextDependency,
) -> AdminMasterSelectResponse:
    validate_web_boundary(request)
    master = select_master_scope(session, context, body.master_user_id)
    return AdminMasterSelectResponse(master=master_card(master))
