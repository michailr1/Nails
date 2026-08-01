from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.schemas.client_linking import (
    ClientLinkNoticeListResponse,
    ClientLinkUndoResponse,
    ClientPhonePreselect,
    ClientReachabilityListResponse,
    GeneralClientInviteResponse,
    PersonalClientInviteResponse,
    PersonalClientLinkRevokeResponse,
)
from app.services.client_linking import (
    create_personal_client_link,
    list_link_notices,
    undo_client_link,
)
from app.services.scheduling_common import SchedulingDomainError
from app.services.web_auth import require_web_session_identity, validate_web_boundary
from app.services.web_client_linking import (
    booking_request_phone_preselect,
    client_invitation_url,
    get_or_create_general_invitation,
    list_client_reachability,
    revoke_open_personal_links,
)
from app.services.web_portal_auth import require_effective_owner_identity

router = APIRouter(prefix="/web/api/client-linking", tags=["web-client-linking"])
SessionDependency = Annotated[Session, Depends(get_db_session)]


def require_read_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_effective_owner_identity(session, request)


def require_write_identity(
    request: Request,
    session: SessionDependency,
) -> RequestIdentity:
    return require_web_session_identity(session, request)


ReadIdentityDependency = Annotated[RequestIdentity, Depends(require_read_identity)]
WriteIdentityDependency = Annotated[RequestIdentity, Depends(require_write_identity)]


def _translate(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


def _require_client_invitation_url(start_token: str) -> str:
    invitation_url = client_invitation_url(start_token)
    if invitation_url is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "client_bot_username_not_configured"},
        )
    return invitation_url


@router.get("/reachability", response_model=ClientReachabilityListResponse)
def reachability(
    session: SessionDependency,
    identity: ReadIdentityDependency,
    connected_only: Annotated[bool, Query()] = False,
) -> ClientReachabilityListResponse:
    return list_client_reachability(
        session,
        identity,
        connected_only=connected_only,
    )


@router.post("/general-link", response_model=GeneralClientInviteResponse)
def general_link_create(
    request: Request,
    session: SessionDependency,
    identity: WriteIdentityDependency,
) -> GeneralClientInviteResponse:
    validate_web_boundary(request)
    try:
        invitation_url = get_or_create_general_invitation(session, identity)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc
    return GeneralClientInviteResponse(invitation_url=invitation_url)


@router.get("/notices", response_model=ClientLinkNoticeListResponse)
def notices(
    session: SessionDependency,
    identity: ReadIdentityDependency,
) -> ClientLinkNoticeListResponse:
    return ClientLinkNoticeListResponse(items=list_link_notices(session, identity))


@router.get(
    "/requests/{booking_request_id}/preselect",
    response_model=ClientPhonePreselect,
)
def request_preselect(
    booking_request_id: uuid.UUID,
    session: SessionDependency,
    identity: ReadIdentityDependency,
) -> ClientPhonePreselect:
    try:
        return booking_request_phone_preselect(
            session,
            identity,
            booking_request_id=booking_request_id,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.post(
    "/clients/{client_id}/personal-link",
    response_model=PersonalClientInviteResponse,
)
def personal_link_create(
    client_id: uuid.UUID,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentityDependency,
) -> PersonalClientInviteResponse:
    validate_web_boundary(request)
    _require_client_invitation_url("config-check")
    try:
        created = create_personal_client_link(
            session,
            identity,
            client_id=client_id,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc
    return PersonalClientInviteResponse(
        invitation_url=_require_client_invitation_url(created.token),
        expires_at=created.expires_at,
        client_id=created.client_id,
    )


@router.post(
    "/clients/{client_id}/personal-link/revoke",
    response_model=PersonalClientLinkRevokeResponse,
)
def personal_link_revoke(
    client_id: uuid.UUID,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentityDependency,
) -> PersonalClientLinkRevokeResponse:
    validate_web_boundary(request)
    try:
        changed = revoke_open_personal_links(
            session,
            identity,
            client_id=client_id,
        )
        return PersonalClientLinkRevokeResponse(changed=changed)
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.post(
    "/notices/{link_record_id}/undo",
    response_model=ClientLinkUndoResponse,
)
def link_undo(
    link_record_id: uuid.UUID,
    request: Request,
    session: SessionDependency,
    identity: WriteIdentityDependency,
) -> ClientLinkUndoResponse:
    validate_web_boundary(request)
    try:
        return undo_client_link(
            session,
            identity,
            link_record_id=link_record_id,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc
