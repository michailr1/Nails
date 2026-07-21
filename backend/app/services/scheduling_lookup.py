from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import Client, ClientProfileStatus, Service, ServiceKind
from app.schemas.scheduling import ServiceListResponse
from app.schemas.scheduling_management import ClientListResponse, ClientLookupResponse
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_presenters import client_card_summary, service_summary


def get_active_service(
    session: Session,
    owner_user_id: uuid.UUID,
    public_name: str,
) -> Service:
    service = session.scalar(
        select(Service).where(
            Service.owner_user_id == owner_user_id,
            Service.normalized_public_name == normalize_public_name(public_name),
            Service.is_active.is_(True),
            Service.kind == ServiceKind.base,
        )
    )
    if service is None:
        raise SchedulingDomainError("service_not_found", status_code=404)
    return service


def get_active_addons(
    session: Session,
    owner_user_id: uuid.UUID,
    public_names: list[str],
) -> list[Service]:
    if not public_names:
        return []

    normalized_names = [normalize_public_name(name) for name in public_names]
    services = session.scalars(
        select(Service).where(
            Service.owner_user_id == owner_user_id,
            Service.normalized_public_name.in_(normalized_names),
            Service.is_active.is_(True),
            Service.kind == ServiceKind.addon,
        )
    ).all()
    by_name = {service.normalized_public_name: service for service in services}
    missing = [
        public_name
        for public_name, normalized in zip(public_names, normalized_names, strict=True)
        if normalized not in by_name
    ]
    if missing:
        raise SchedulingDomainError(
            "addon_not_found",
            status_code=404,
            details={"missing_names": missing},
        )
    return [by_name[normalized] for normalized in normalized_names]


def get_active_client(
    session: Session,
    owner_user_id: uuid.UUID,
    public_name: str,
) -> Client:
    client = session.scalar(
        select(Client).where(
            Client.owner_user_id == owner_user_id,
            Client.normalized_public_name == normalize_public_name(public_name),
            Client.profile_status == ClientProfileStatus.active,
        )
    )
    if client is None:
        raise SchedulingDomainError("client_not_found", status_code=404)
    return client


def get_active_client_by_id(
    session: Session,
    owner_user_id: uuid.UUID,
    client_id: uuid.UUID,
) -> Client:
    client = session.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.owner_user_id == owner_user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
    )
    if client is None:
        raise SchedulingDomainError("client_not_found", status_code=404)
    return client


def list_active_services(
    session: Session,
    identity: RequestIdentity,
) -> ServiceListResponse:
    services = session.scalars(
        select(Service)
        .where(
            Service.owner_user_id == identity.user_id,
            Service.is_active.is_(True),
        )
        .order_by(Service.public_name)
    ).all()
    return ServiceListResponse(services=[service_summary(service) for service in services])


def list_active_clients(
    session: Session,
    identity: RequestIdentity,
) -> ClientListResponse:
    clients = session.scalars(
        select(Client)
        .where(
            Client.owner_user_id == identity.user_id,
            Client.profile_status == ClientProfileStatus.active,
        )
        .order_by(Client.public_name)
    ).all()
    return ClientListResponse(clients=[client_card_summary(client) for client in clients])


def find_client_exact(
    session: Session,
    identity: RequestIdentity,
    public_name: str,
) -> ClientLookupResponse:
    client = session.scalar(
        select(Client).where(
            Client.owner_user_id == identity.user_id,
            Client.normalized_public_name == normalize_public_name(public_name),
            Client.profile_status == ClientProfileStatus.active,
        )
    )
    if client is None:
        return ClientLookupResponse(found=False)
    return ClientLookupResponse(found=True, client=client_card_summary(client))
