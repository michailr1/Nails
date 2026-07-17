from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.db import get_db_session
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
    clear_auth_cookies,
    consume_challenge,
    logout_web_session,
    require_web_session_identity,
    set_session_cookie,
    set_start_cookies,
    start_challenge,
)
from app.services.web_auth_limits import (
    enforce_approval_server_rate_limit,
    enforce_consume_rate_limit,
    enforce_status_rate_limit,
    invalidate_pending_browser_challenge,
    read_bound_challenge_status,
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
    invalidate_pending_browser_challenge(session, request)
    started = start_challenge(session, request)
    set_start_cookies(response, started)
    return ChallengeStartResponse(
        challenge_id=started.challenge.id,
        confirmation_code=started.confirmation_code,
        expires_at=started.challenge.expires_at,
        csrf_token=started.csrf_token,
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
    enforce_status_rate_limit(session, request, challenge_id)
    challenge = read_bound_challenge_status(session, request, challenge_id)
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
    enforce_consume_rate_limit(session, request, body.challenge_id)
    result = consume_challenge(session, request, body.challenge_id)
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
    if not enforce_approval_server_rate_limit(session, identity):
        return TelegramChallengeApproveResponse(approved=False)
    return TelegramChallengeApproveResponse(
        approved=approve_challenge(
            session,
            identity=identity,
            confirmation_code=body.confirmation_code,
        )
    )


@router.get("/web/api/auth/session", response_model=WebSessionStateResponse)
def session_state(
    request: Request,
    response: Response,
    session: SessionDependency,
) -> WebSessionStateResponse:
    try:
        require_web_session_identity(session, request)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            clear_auth_cookies(response)
        raise
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
