from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, Client, ClientProfileStatus
from app.schemas.scheduling import ClientCreateRequest, ClientCreateResponse
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import SchedulingDomainError, lock_owner_schedule
from app.services.scheduling_presenters import client_summary


def create_or_reuse_client(
    session: Session,
    identity: RequestIdentity,
    body: ClientCreateRequest,
) -> ClientCreateResponse:
    normalized = normalize_public_name(body.public_name)
    lock_owner_schedule(session, identity.user_id)
    client = session.scalar(
        select(Client)
        .where(
            Client.owner_user_id == identity.user_id,
            Client.normalized_public_name == normalized,
            Client.profile_status == ClientProfileStatus.active,
        )
        .with_for_update()
    )

    if client is not None:
        if body.phone and client.phone and body.phone != client.phone:
            raise SchedulingDomainError("client_contact_conflict")
        contact_added = False
        if body.phone and client.phone is None:
            client.phone = body.phone
            contact_added = True
            session.add(
                AuditEvent(
                    owner_user_id=identity.user_id,
                    actor_user_id=identity.user_id,
                    action="client.contact_added",
                    object_type="client",
                    object_id=client.id,
                    request_id=identity.request_id,
                    safe_changes={"contact_present": True},
                )
            )
            session.commit()
        return ClientCreateResponse(
            client=client_summary(client),
            created=False,
            contact_added=contact_added,
        )

    client = Client(
        owner_user_id=identity.user_id,
        public_name=body.public_name,
        normalized_public_name=normalized,
        phone=body.phone,
        profile_status=ClientProfileStatus.active,
    )
    session.add(client)
    session.flush()
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="client.created",
            object_type="client",
            object_id=client.id,
            request_id=identity.request_id,
            safe_changes={"contact_present": body.phone is not None},
        )
    )
    session.commit()
    return ClientCreateResponse(client=client_summary(client), created=True)
