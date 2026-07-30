from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity, require_client_transport_identity
from app.client_models import MasterPublicProfile
from app.db import get_db_session
from app.schemas.client_contour import (
    ClientContextResponse,
    ClientEntryState,
    ClientMasterProjection,
    ClientStartRequest,
)
from app.schemas.client_linking import (
    ConfirmedTelegramContactRequest,
    ConfirmedTelegramContactResponse,
    ManualPhoneHintRequest,
    ManualPhoneHintResponse,
)
from app.services.client_context_selection import remember_client_binding
from app.services.client_linking import (
    confirm_telegram_contact,
    consume_personal_client_link,
    set_manual_phone_hint,
)
from app.services.scheduling_common import SchedulingDomainError

router = APIRouter(prefix="/api/v1/client/linking", tags=["client-linking"])
SessionDependency = Annotated[Session, Depends(get_db_session)]
ClientIdentityDependency = Annotated[
    ClientTransportIdentity,
    Depends(require_client_transport_identity),
]
BindingHeader = Annotated[str, Header(alias="X-Client-Binding-ID", min_length=1)]


def _binding_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_client_binding_id"},
        ) from exc


def _translate(exc: SchedulingDomainError) -> HTTPException:
    detail: dict[str, object] = {"code": exc.code}
    if exc.details is not None:
        detail["details"] = exc.details
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.post(
    "/confirmed-contact",
    response_model=ConfirmedTelegramContactResponse,
)
def confirmed_contact(
    body: ConfirmedTelegramContactRequest,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ConfirmedTelegramContactResponse:
    try:
        return confirm_telegram_contact(
            session,
            identity,
            binding_id=_binding_id(binding_header),
            contact_user_id=body.contact_user_id,
            phone_number=body.phone_number,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.put("/phone-hint", response_model=ManualPhoneHintResponse)
def phone_hint(
    body: ManualPhoneHintRequest,
    session: SessionDependency,
    identity: ClientIdentityDependency,
    binding_header: BindingHeader,
) -> ManualPhoneHintResponse:
    try:
        return set_manual_phone_hint(
            session,
            identity,
            binding_id=_binding_id(binding_header),
            phone_number=body.phone_number,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc


@router.post("/personal-start", response_model=ClientContextResponse)
def personal_start(
    body: ClientStartRequest,
    session: SessionDependency,
    identity: ClientIdentityDependency,
) -> ClientContextResponse:
    try:
        owner_user_id, binding = consume_personal_client_link(
            session,
            identity,
            token=body.start_token,
            requested_public_name=body.requested_public_name,
        )
        profile = session.get(MasterPublicProfile, owner_user_id)
        if profile is None or not profile.display_name.strip():
            raise SchedulingDomainError("master_link_inactive", status_code=409)
        master = ClientMasterProjection(
            binding_id=binding.id,
            display_name=profile.display_name.strip(),
            public_contact=(
                profile.public_contact.strip() if profile.public_contact else None
            ),
        )
        remember_client_binding(session, identity, binding_id=binding.id)
        return ClientContextResponse(
            state=ClientEntryState.ready,
            message=(
                f"👋 Здравствуйте! Вы записываетесь к **{master.display_name}**.\n"
                "[💅 Прайс] [📅 Записаться] [🗂 Мои записи]"
            ),
            master=master,
        )
    except SchedulingDomainError as exc:
        raise _translate(exc) from exc
