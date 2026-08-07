from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity
from app.client_models import (
    ClientTelegramIdentity,
    ClientTelegramIdentityStatus,
    MasterPublicProfile,
)
from app.models import AuditEvent, Service, User, UserRole
from app.schemas.client_contour import (
    ClientContextResponse,
    ClientEntryState,
    ClientMasterProjection,
    ClientPublicCatalogItem,
    ClientPublicCatalogResponse,
    ClientPublicSlotsResponse,
    ClientStartRequest,
)
from app.services.client_binding import ClientBindingError, resolve_start_token
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_queries import find_free_slots_for_owner
from app.timezones import owner_timezone_name

NO_BINDING_MESSAGE = (
    "👋 Здравствуйте! Это бот для записи к мастеру. Запись открывается по личной "
    "ссылке вашего мастера — обычно она в его профиле, сторис или визитке. "
    "Откройте эту ссылку — и я покажу запись именно к вашему мастеру. Если "
    "ссылки нет — попросите у мастера «ссылку для записи»."
)
INVALID_LINK_MESSAGE = (
    "Эта ссылка больше не действует. Попросите у мастера актуальную ссылку "
    "для записи 🙏"
)
REVOKED_MESSAGE = (
    "Запись к этому мастеру сейчас недоступна. Если это ошибка — свяжитесь "
    "с мастером напрямую."
)
CHOOSE_MASTER_MESSAGE = "Выберите мастера из списка «Ваши мастера»."


@dataclass(frozen=True, slots=True)
class ClientBindingContext:
    owner_user_id: uuid.UUID
    binding: ClientTelegramIdentity
    master: ClientMasterProjection


def _welcome(display_name: str) -> str:
    return (
        f"👋 Здравствуйте! Вы записываетесь к **{display_name}**.\n"
        "[💅 Прайс] [📅 Записаться] [🗂 Мои записи]"
    )


def _lock_identity(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    telegram_user_id: int,
) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:identity_key, 1))"),
        {"identity_key": f"{owner_user_id}:{telegram_user_id}"},
    )


def _binding_for_owner(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    telegram_user_id: int,
    lock: bool = False,
) -> ClientTelegramIdentity | None:
    statement = select(ClientTelegramIdentity).where(
        ClientTelegramIdentity.owner_user_id == owner_user_id,
        ClientTelegramIdentity.telegram_user_id == telegram_user_id,
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _projection(
    session: Session,
    row: ClientTelegramIdentity,
    profile: MasterPublicProfile,
) -> ClientMasterProjection:
    return ClientMasterProjection(
        binding_id=row.id,
        display_name=profile.display_name.strip(),
        public_contact=profile.public_contact.strip() if profile.public_contact else None,
        timezone=owner_timezone_name(session, row.owner_user_id),
    )


def _available_projection(
    session: Session,
    row: ClientTelegramIdentity,
) -> ClientMasterProjection | None:
    owner = session.get(User, row.owner_user_id)
    if owner is None or owner.role != UserRole.master or not owner.is_active:
        return None
    profile = session.get(MasterPublicProfile, row.owner_user_id)
    if profile is None or not profile.display_name.strip():
        return None
    return _projection(session, row, profile)


def start_client_context(
    session: Session,
    identity: ClientTransportIdentity,
    body: ClientStartRequest,
) -> ClientContextResponse:
    try:
        resolved = resolve_start_token(
            session,
            start_token=body.start_token,
            telegram_user_id=identity.telegram_user_id,
        )
    except ClientBindingError as exc:
        if exc.code == "invalid_master_link":
            return ClientContextResponse(
                state=ClientEntryState.invalid_link,
                message=INVALID_LINK_MESSAGE,
            )
        return ClientContextResponse(
            state=ClientEntryState.revoked,
            message=REVOKED_MESSAGE,
        )

    owner_user_id = resolved.owner_user_id
    if not isinstance(owner_user_id, uuid.UUID):
        raise SchedulingDomainError("client_owner_invalid", status_code=500)

    _lock_identity(
        session,
        owner_user_id=owner_user_id,
        telegram_user_id=identity.telegram_user_id,
    )
    row = _binding_for_owner(
        session,
        owner_user_id=owner_user_id,
        telegram_user_id=identity.telegram_user_id,
        lock=True,
    )
    created = row is None
    changed = False
    if row is None:
        row = ClientTelegramIdentity(
            owner_user_id=owner_user_id,
            telegram_user_id=identity.telegram_user_id,
            status=ClientTelegramIdentityStatus.pending,
            requested_public_name=body.requested_public_name,
        )
        session.add(row)
        session.flush()
        changed = True
    elif row.status == ClientTelegramIdentityStatus.revoked:
        return ClientContextResponse(
            state=ClientEntryState.revoked,
            message=REVOKED_MESSAGE,
        )
    elif (
        row.status == ClientTelegramIdentityStatus.pending
        and row.requested_public_name != body.requested_public_name
    ):
        row.requested_public_name = body.requested_public_name
        changed = True

    profile = session.get(MasterPublicProfile, owner_user_id)
    if profile is None or not profile.display_name.strip():
        raise SchedulingDomainError("master_link_inactive", status_code=409)

    if created or changed:
        session.add(
            AuditEvent(
                owner_user_id=owner_user_id,
                actor_user_id=None,
                action=(
                    "client_identity.registered"
                    if created
                    else "client_identity.updated"
                ),
                object_type="client_telegram_identity",
                object_id=row.id,
                request_id=identity.request_id,
                safe_changes={
                    "actor_type": "client_platform_bot",
                    "status": str(row.status),
                    "changed_fields": ["requested_public_name"],
                },
            )
        )
    session.commit()
    master = _projection(session, row, profile)
    return ClientContextResponse(
        state=ClientEntryState.ready,
        message=_welcome(master.display_name),
        master=master,
    )


def get_client_context(
    session: Session,
    identity: ClientTransportIdentity,
) -> ClientContextResponse:
    rows = session.scalars(
        select(ClientTelegramIdentity)
        .join(User, User.id == ClientTelegramIdentity.owner_user_id)
        .join(
            MasterPublicProfile,
            MasterPublicProfile.owner_user_id == ClientTelegramIdentity.owner_user_id,
        )
        .where(
            ClientTelegramIdentity.telegram_user_id == identity.telegram_user_id,
            ClientTelegramIdentity.status.in_(
                (
                    ClientTelegramIdentityStatus.pending,
                    ClientTelegramIdentityStatus.active,
                )
            ),
            User.role == UserRole.master,
            User.is_active.is_(True),
        )
        .order_by(MasterPublicProfile.display_name, ClientTelegramIdentity.id)
    ).all()
    masters = [
        projection
        for row in rows
        if (projection := _available_projection(session, row)) is not None
    ]
    if not masters:
        return ClientContextResponse(
            state=ClientEntryState.no_binding,
            message=NO_BINDING_MESSAGE,
        )
    if len(masters) == 1:
        master = masters[0]
        return ClientContextResponse(
            state=ClientEntryState.ready,
            message=_welcome(master.display_name),
            master=master,
        )
    return ClientContextResponse(
        state=ClientEntryState.choose_master,
        message=CHOOSE_MASTER_MESSAGE,
        masters=masters,
    )


def require_client_binding(
    session: Session,
    identity: ClientTransportIdentity,
    *,
    binding_id: uuid.UUID,
) -> ClientBindingContext:
    row = session.scalar(
        select(ClientTelegramIdentity).where(
            ClientTelegramIdentity.id == binding_id,
            ClientTelegramIdentity.telegram_user_id == identity.telegram_user_id,
        )
    )
    if row is None:
        raise SchedulingDomainError("client_binding_not_found", status_code=404)
    if row.status == ClientTelegramIdentityStatus.revoked:
        raise SchedulingDomainError("client_identity_revoked", status_code=403)
    projection = _available_projection(session, row)
    if projection is None:
        raise SchedulingDomainError("master_unavailable", status_code=403)
    return ClientBindingContext(
        owner_user_id=row.owner_user_id,
        binding=row,
        master=projection,
    )


def _public_service(service: Service) -> ClientPublicCatalogItem:
    return ClientPublicCatalogItem(
        public_name=service.public_name,
        public_description=service.public_description,
        kind=service.kind,
        price_type=service.price_type,
        price_amount=(
            service.price_amount
            if service.price_type in {"fixed", "per_unit"}
            else None
        ),
        price_min_amount=service.price_min_amount,
        price_max_amount=service.price_max_amount,
        price_unit=service.price_unit,
        currency=service.currency,
        duration_minutes=service.duration_minutes if service.kind == "base" else None,
        extra_minutes=service.extra_minutes,
        category=service.category,
        sort_order=service.sort_order,
    )


def list_public_catalog(
    session: Session,
    context: ClientBindingContext,
) -> ClientPublicCatalogResponse:
    services = session.scalars(
        select(Service)
        .where(
            Service.owner_user_id == context.owner_user_id,
            Service.is_active.is_(True),
        )
        .order_by(
            func.coalesce(Service.category, ""),
            Service.sort_order,
            Service.public_name,
        )
    ).all()
    return ClientPublicCatalogResponse(
        master=context.master,
        services=[_public_service(service) for service in services],
    )


def find_public_slots(
    session: Session,
    context: ClientBindingContext,
    day: date,
    service_name: str,
) -> ClientPublicSlotsResponse:
    result = find_free_slots_for_owner(
        session,
        context.owner_user_id,
        day,
        service_name,
    )
    return ClientPublicSlotsResponse(
        master=context.master,
        day=result.day,
        timezone=result.timezone,
        weekday_iso=result.weekday_iso,
        availability_known=result.availability_known,
        is_working=result.is_working,
        step_minutes=result.step_minutes,
        service=ClientPublicCatalogItem(
            public_name=result.service.public_name,
            public_description=result.service.public_description,
            kind=result.service.kind,
            price_type=result.service.price_type,
            price_amount=result.service.price_amount,
            price_min_amount=result.service.price_min_amount,
            price_max_amount=result.service.price_max_amount,
            price_unit=result.service.price_unit,
            currency=result.service.currency,
            duration_minutes=result.service.duration_minutes,
            extra_minutes=result.service.extra_minutes,
            category=result.service.category,
            sort_order=result.service.sort_order,
        ),
        starts_at=result.starts_at,
    )
