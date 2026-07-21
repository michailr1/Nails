from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import ClientRequestIdentity
from app.client_models import ClientTelegramIdentity, ClientTelegramIdentityStatus
from app.models import AuditEvent, Client, Service
from app.schemas.client_contour import (
    ClientIdentityLookupResponse,
    ClientIdentitySummary,
    ClientIdentityUpsertRequest,
    ClientIdentityUpsertResponse,
    ClientPublicCatalogItem,
    ClientPublicCatalogResponse,
    ClientPublicSlotsResponse,
)
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_queries import find_free_slots_for_owner


def _public_service(service: Service) -> ClientPublicCatalogItem:
    return ClientPublicCatalogItem(
        public_name=service.public_name,
        public_description=service.public_description,
        kind=service.kind,
        price_type=service.price_type,
        price_amount=(
            service.price_amount if service.price_type in {"fixed", "per_unit"} else None
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
    identity: ClientRequestIdentity,
) -> ClientPublicCatalogResponse:
    services = session.scalars(
        select(Service)
        .where(
            Service.owner_user_id == identity.owner_user_id,
            Service.is_active.is_(True),
        )
        .order_by(
            func.coalesce(Service.category, ""),
            Service.sort_order,
            Service.public_name,
        )
    ).all()
    return ClientPublicCatalogResponse(
        services=[_public_service(service) for service in services]
    )


def find_public_slots(
    session: Session,
    identity: ClientRequestIdentity,
    day: date,
    service_name: str,
) -> ClientPublicSlotsResponse:
    result = find_free_slots_for_owner(
        session,
        identity.owner_user_id,
        day,
        service_name,
    )
    return ClientPublicSlotsResponse(
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


def _lock_client_identity(
    session: Session,
    identity: ClientRequestIdentity,
) -> None:
    session.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended(:identity_key, 1)"
            ")"
        ),
        {
            "identity_key": (
                f"{identity.owner_user_id}:{identity.telegram_user_id}"
            )
        },
    )


def _get_identity(
    session: Session,
    identity: ClientRequestIdentity,
    *,
    lock: bool = False,
) -> ClientTelegramIdentity | None:
    statement = select(ClientTelegramIdentity).where(
        ClientTelegramIdentity.owner_user_id == identity.owner_user_id,
        ClientTelegramIdentity.telegram_user_id == identity.telegram_user_id,
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _identity_summary(
    session: Session,
    row: ClientTelegramIdentity,
) -> ClientIdentitySummary:
    display_name = row.requested_public_name
    if row.status == ClientTelegramIdentityStatus.active and row.client_id is not None:
        linked_name = session.scalar(
            select(Client.public_name).where(
                Client.id == row.client_id,
                Client.owner_user_id == row.owner_user_id,
            )
        )
        if linked_name is not None:
            display_name = linked_name
    return ClientIdentitySummary(
        status=ClientTelegramIdentityStatus(row.status),
        display_name=display_name,
        phone_shared=row.requested_phone is not None,
        linked=row.client_id is not None,
    )


def get_client_identity(
    session: Session,
    identity: ClientRequestIdentity,
) -> ClientIdentityLookupResponse:
    row = _get_identity(session, identity)
    if row is None:
        return ClientIdentityLookupResponse(found=False)
    return ClientIdentityLookupResponse(
        found=True,
        identity=_identity_summary(session, row),
    )


def upsert_client_identity(
    session: Session,
    identity: ClientRequestIdentity,
    body: ClientIdentityUpsertRequest,
) -> ClientIdentityUpsertResponse:
    if body.contact_user_id is not None and body.contact_user_id != identity.telegram_user_id:
        raise SchedulingDomainError("client_contact_mismatch", status_code=400)

    _lock_client_identity(session, identity)
    row = _get_identity(session, identity, lock=True)
    created = row is None
    changed_fields: list[str] = []

    if row is None:
        row = ClientTelegramIdentity(
            owner_user_id=identity.owner_user_id,
            telegram_user_id=identity.telegram_user_id,
            status=ClientTelegramIdentityStatus.pending,
            requested_public_name=body.requested_public_name,
            requested_phone=body.requested_phone,
        )
        session.add(row)
        session.flush()
        changed_fields = ["requested_public_name"]
        if body.requested_phone is not None:
            changed_fields.append("requested_phone")
    elif row.status == ClientTelegramIdentityStatus.revoked:
        raise SchedulingDomainError("client_identity_revoked", status_code=403)
    elif row.status == ClientTelegramIdentityStatus.pending:
        if row.requested_public_name != body.requested_public_name:
            row.requested_public_name = body.requested_public_name
            changed_fields.append("requested_public_name")
        if row.requested_phone != body.requested_phone:
            row.requested_phone = body.requested_phone
            changed_fields.append("requested_phone")

    if created or changed_fields:
        session.add(
            AuditEvent(
                owner_user_id=identity.owner_user_id,
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
                    "actor_type": "client_bot",
                    "status": row.status,
                    "phone_shared": row.requested_phone is not None,
                    "changed_fields": sorted(changed_fields),
                },
            )
        )
    session.commit()
    return ClientIdentityUpsertResponse(
        identity=_identity_summary(session, row),
        created=created,
        changed=created or bool(changed_fields),
    )
