from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import RequestIdentity, require_request_identity
from app.db import get_db_session
from app.models import OnboardingSection
from app.schemas.onboarding import DraftUpdateRequest, OnboardingStateResponse
from app.services.onboarding import (
    OnboardingDomainError,
    complete_onboarding,
    confirm_section,
    get_onboarding_state,
    pause_onboarding,
    resume_onboarding,
    save_draft,
    start_onboarding,
)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

SessionDependency = Annotated[Session, Depends(get_db_session)]
IdentityDependency = Annotated[RequestIdentity, Depends(require_request_identity)]


def _translate_domain_error(exc: OnboardingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.post("/start", response_model=OnboardingStateResponse)
def start(
    session: SessionDependency,
    identity: IdentityDependency,
) -> OnboardingStateResponse:
    try:
        return start_onboarding(session, identity)
    except OnboardingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.get("", response_model=OnboardingStateResponse)
def get_state(
    session: SessionDependency,
    identity: IdentityDependency,
) -> OnboardingStateResponse:
    try:
        return get_onboarding_state(session, identity)
    except OnboardingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.put("/sections/{section}", response_model=OnboardingStateResponse)
def update_section(
    section: OnboardingSection,
    body: DraftUpdateRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> OnboardingStateResponse:
    try:
        return save_draft(session, identity, section, body.payload)
    except OnboardingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post("/sections/{section}/confirm", response_model=OnboardingStateResponse)
def confirm(
    section: OnboardingSection,
    session: SessionDependency,
    identity: IdentityDependency,
) -> OnboardingStateResponse:
    try:
        return confirm_section(session, identity, section)
    except OnboardingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post("/pause", response_model=OnboardingStateResponse)
def pause(
    session: SessionDependency,
    identity: IdentityDependency,
) -> OnboardingStateResponse:
    try:
        return pause_onboarding(session, identity)
    except OnboardingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post("/resume", response_model=OnboardingStateResponse)
def resume(
    session: SessionDependency,
    identity: IdentityDependency,
) -> OnboardingStateResponse:
    try:
        return resume_onboarding(session, identity)
    except OnboardingDomainError as exc:
        raise _translate_domain_error(exc) from exc


@router.post("/complete", response_model=OnboardingStateResponse)
def complete(
    session: SessionDependency,
    identity: IdentityDependency,
) -> OnboardingStateResponse:
    try:
        return complete_onboarding(session, identity)
    except OnboardingDomainError as exc:
        raise _translate_domain_error(exc) from exc
