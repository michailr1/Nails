from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import Client, ClientProfileStatus, Service
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
        )
    )
    if service is None:
        raise SchedulingDomainError("service_not_found", status_code=404)
    return service


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
