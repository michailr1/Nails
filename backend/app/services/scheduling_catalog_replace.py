from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, Service
from app.schemas.scheduling_catalog_replace import (
    CatalogReplaceRequest,
    CatalogReplaceResponse,
)
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import lock_owner_schedule
from app.services.scheduling_presenters import service_summary
from app.services.scheduling_services import (
    _SERVICE_FIELDS,
    _ensure_catalog_write_shape,
    _service_values,
)


def replace_catalog(
    session: Session,
    identity: RequestIdentity,
    body: CatalogReplaceRequest,
) -> CatalogReplaceResponse:
    for definition in body.services:
        _ensure_catalog_write_shape(definition)

    lock_owner_schedule(session, identity.user_id)
    existing_services = session.scalars(
        select(Service)
        .where(Service.owner_user_id == identity.user_id)
        .with_for_update()
    ).all()
    existing_by_name = {
        service.normalized_public_name: service for service in existing_services
    }

    created_count = 0
    updated_count = 0
    desired_names: set[str] = set()

    for definition in body.services:
        desired = _service_values(definition)
        normalized_name = normalize_public_name(definition.public_name)
        desired_names.add(normalized_name)
        service = existing_by_name.get(normalized_name)
        if service is None:
            session.add(Service(owner_user_id=identity.user_id, **desired))
            created_count += 1
            continue

        changed = False
        for field in (*_SERVICE_FIELDS, "normalized_public_name"):
            value = desired[field]
            if getattr(service, field) != value:
                setattr(service, field, value)
                changed = True
        if changed:
            updated_count += 1

    archived_count = 0
    for service in existing_services:
        if service.normalized_public_name in desired_names or not service.is_active:
            continue
        service.is_active = False
        archived_count += 1

    changed = any((created_count, updated_count, archived_count))
    if changed:
        session.flush()
        session.add(
            AuditEvent(
                owner_user_id=identity.user_id,
                actor_user_id=identity.user_id,
                action="service.catalog_replaced",
                object_type="service_catalog",
                object_id=None,
                request_id=identity.request_id,
                safe_changes={
                    "created_count": created_count,
                    "updated_count": updated_count,
                    "archived_count": archived_count,
                    "active_count": len(body.services),
                },
            )
        )
    session.commit()
    session.expire_all()

    services = session.scalars(
        select(Service)
        .where(
            Service.owner_user_id == identity.user_id,
            Service.is_active.is_(True),
        )
        .order_by(
            func.coalesce(Service.category, ""),
            Service.sort_order,
            Service.public_name,
        )
    ).all()
    return CatalogReplaceResponse(
        changed=changed,
        created_count=created_count,
        updated_count=updated_count,
        archived_count=archived_count,
        services=[service_summary(service) for service in services],
        verified=True,
    )
