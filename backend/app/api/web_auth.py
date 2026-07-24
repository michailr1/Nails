from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
from app.models import UserRole
from app.schemas.web_auth import (
    ChallengeConsumeRequest,
    ChallengeConsumeResponse,
    ChallengeStartResponse,
    ChallengeStatusResponse,
    LogoutResponse,
    TelegramChallengeApproveRequest,
    TelegramChallengeApproveResponse,
    WebSessionStateResponse,
)
from app.services.web_auth import (
    approve_challenge,
    challenge_status,
    clear_auth_cookies,
    logout_web_session,
    set_session_cookie,
    set_start_cookies,
    start_challenge,
)
from app.services.web_portal_auth import (
    consume_portal_challenge,
    require_portal_session_context,
)
from app.web_auth_identity import require_web_approval_identity

router = APIRouter(tags=["web-auth"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
WebApprovalIdentityDependency = Annotated[
    RequestIdentity | None,
    Depends(require_web_approval_identity),
]


@router.post(
    "/web/api/auth/challenges",
    response_model=ChallengeStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_challenge(
    request: Request,
    response: Response,
    session: SessionDependency,
) -> ChallengeStartResponse:
    started = start_challenge(session, request)
    set_start_cookies(response, started)
    return ChallengeStartResponse(
        challenge_id=started.challenge.id,
        verification_number=started.verification_number,
        expires_at=started.challenge.expires_at,
    )


@router.get(
    "/web/api/auth/challenges/{challenge_id}",
    response_model=ChallengeStatusResponse,
)
def get_challenge_status(
    challenge_id: uuid.UUID,
    request: Request,
    session: SessionDependency,
) -> ChallengeStatusResponse:
    challenge = challenge_status(session, request, challenge_id)
    return ChallengeStatusResponse(
        challenge_id=challenge.challenge_id,
        status=challenge.status,
        expires_at=challenge.expires_at,
    )


@router.post(
    "/web/api/auth/challenges/consume",
    response_model=ChallengeConsumeResponse,
)
def consume(
    body: ChallengeConsumeRequest,
    request: Request,
    response: Response,
    session: SessionDependency,
) -> ChallengeConsumeResponse:
    result = consume_portal_challenge(session, request, body.challenge_id)
    if result.authenticated and result.session_token is not None:
        set_session_cookie(response, result.session_token)
    return ChallengeConsumeResponse(
        authenticated=result.authenticated,
        status=result.status,
    )


@router.post(
    "/api/v1/web-auth/challenges/approve",
    response_model=TelegramChallengeApproveResponse,
)
def approve_from_telegram(
    body: TelegramChallengeApproveRequest,
    session: SessionDependency,
    identity: WebApprovalIdentityDependency,
) -> TelegramChallengeApproveResponse:
    if identity is None:
        return TelegramChallengeApproveResponse(approved=False)
    return TelegramChallengeApproveResponse(
        approved=approve_challenge(
            session,
            identity=identity,
            challenge_id=body.challenge_id,
            verification_number=body.verification_number,
        )
    )


@router.get(
    "/web/api/auth/session",
    response_model=WebSessionStateResponse,
    response_model_exclude_unset=True,
)
def session_state(
    request: Request,
    session: SessionDependency,
) -> WebSessionStateResponse | JSONResponse:
    try:
        context = require_portal_session_context(session, request)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": {"code": "unauthorized"}},
        )
        clear_auth_cookies(response)
        return response
    if context.identity.role == UserRole.admin:
        return WebSessionStateResponse(
            authenticated=True,
            role=UserRole.admin.value,
            target_owner_user_id=context.web_session.target_owner_user_id,
        )
    return WebSessionStateResponse(authenticated=True)


@router.post("/web/api/auth/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    session: SessionDependency,
) -> LogoutResponse:
    logout_web_session(session, request)
    clear_auth_cookies(response)
    return LogoutResponse(logged_out=True)
