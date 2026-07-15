from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, Client, ClientProfileStatus
from app.schemas.scheduling_management import (
    ClientCreateRequest,
    ClientCreateResponse,
    ClientReplaceRequest,
    ClientReplaceResponse,
)
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import SchedulingDomainError, lock_owner_schedule
from app.services.scheduling_presenters import client_card_summary

_CLIENT_FIELDS = (
    "public_name",
    "phone",
    "private_alias",
    "contact_channel",
    "birthday",
    "notes",
    "nail_skin_notes",
    "sensitivity_notes",
    "style_preferences",
    "communication_preferences",
)


def _client_values(body: ClientCreateRequest | ClientReplaceRequest) -> dict[str, Any]:
    return {field: getattr(body, field) for field in _CLIENT_FIELDS}


def _get_active_client(
    session: Session,
    identity: RequestIdentity,
    public_name: str,
    *,
    lock: bool,
) -> Client | None:
    statement = select(Client).where(
        Client.owner_user_id == identity.user_id,
        Client.normalized_public_name == normalize_public_name(public_name),
        Client.profile_status == ClientProfileStatus.active,
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def create_or_reuse_client(
    session: Session,
    identity: RequestIdentity,
    body: ClientCreateRequest,
) -> ClientCreateResponse:
    lock_owner_schedule(session, identity.user_id)
    client = _get_active_client(session, identity, body.public_name, lock=True)

    if client is not None:
        if body.phone and client.phone and body.phone != client.phone:
            raise SchedulingDomainError("client_contact_conflict")
        supplied_private_fields = {
            field
            for field in _CLIENT_FIELDS
            if field not in {"public_name", "phone"} and getattr(body, field) is not None
        }
        if any(getattr(client, field) != getattr(body, field) for field in supplied_private_fields):
            raise SchedulingDomainError("client_profile_conflict")

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
                    safe_changes={"changed_fields": ["phone"]},
                )
            )
            session.commit()
        return ClientCreateResponse(
            client=client_card_summary(client),
            created=False,
            contact_added=contact_added,
        )

    values = _client_values(body)
    client = Client(
        owner_user_id=identity.user_id,
        normalized_public_name=normalize_public_name(body.public_name),
        profile_status=ClientProfileStatus.active,
        **values,
    )
    session.add(client)
    session.flush()
    present_fields = sorted(field for field, value in values.items() if value is not None)
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="client.created",
            object_type="client",
            object_id=client.id,
            request_id=identity.request_id,
            safe_changes={"changed_fields": present_fields},
        )
    )
    session.commit()
    return ClientCreateResponse(client=client_card_summary(client), created=True)


def replace_client(
    session: Session,
    identity: RequestIdentity,
    body: ClientReplaceRequest,
) -> ClientReplaceResponse:
    lock_owner_schedule(session, identity.user_id)
    client = _get_active_client(session, identity, body.current_public_name, lock=True)
    if client is None:
        raise SchedulingDomainError("client_not_found", status_code=404)

    desired = _client_values(body)
    desired_normalized_name = normalize_public_name(body.public_name)
    if desired_normalized_name != client.normalized_public_name:
        conflict = session.scalar(
            select(Client.id)
            .where(
                Client.owner_user_id == identity.user_id,
                Client.normalized_public_name == desired_normalized_name,
                Client.profile_status == ClientProfileStatus.active,
                Client.id != client.id,
            )
            .limit(1)
        )
        if conflict is not None:
            raise SchedulingDomainError("client_name_conflict")

    changed_fields: list[str] = []
    for field in _CLIENT_FIELDS:
        value = desired[field]
        if getattr(client, field) != value:
            setattr(client, field, value)
            changed_fields.append(field)
    if client.normalized_public_name != desired_normalized_name:
        client.normalized_public_name = desired_normalized_name

    if changed_fields:
        session.add(
            AuditEvent(
                owner_user_id=identity.user_id,
                actor_user_id=identity.user_id,
                action="client.updated",
                object_type="client",
                object_id=client.id,
                request_id=identity.request_id,
                safe_changes={"changed_fields": sorted(changed_fields)},
            )
        )
    session.commit()
    return ClientReplaceResponse(
        client=client_card_summary(client),
        changed=bool(changed_fields),
        changed_fields=sorted(changed_fields),
    )
