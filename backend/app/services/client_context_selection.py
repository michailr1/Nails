from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity
from app.client_models import ClientTelegramContext
from app.schemas.client_contour import (
    ClientContextResponse,
    ClientEntryState,
    ClientMasterProjection,
)
from app.services.client_contour import require_client_binding


def _welcome(display_name: str) -> str:
    return (
        f"👋 Здравствуйте! Вы записываетесь к **{display_name}**.\n"
        "[💅 Прайс] [📅 Записаться] [🗂 Мои записи]"
    )


def remember_client_binding(
    session: Session,
    identity: ClientTransportIdentity,
    *,
    binding_id: uuid.UUID,
) -> ClientMasterProjection:
    binding = require_client_binding(
        session,
        identity,
        binding_id=binding_id,
    )
    context = session.get(ClientTelegramContext, identity.telegram_user_id)
    if context is None:
        context = ClientTelegramContext(
            telegram_user_id=identity.telegram_user_id,
            active_binding_id=binding.binding.id,
        )
        session.add(context)
    else:
        context.active_binding_id = binding.binding.id
    session.commit()
    return binding.master


def apply_sticky_context(
    session: Session,
    identity: ClientTransportIdentity,
    response: ClientContextResponse,
) -> ClientContextResponse:
    if response.state != ClientEntryState.choose_master:
        return response

    context = session.get(ClientTelegramContext, identity.telegram_user_id)
    if context is None:
        return response

    for master in response.masters:
        if master.binding_id == context.active_binding_id:
            return ClientContextResponse(
                state=ClientEntryState.ready,
                message=_welcome(master.display_name),
                master=master,
            )
    return response
