from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, Service
from app.schemas.scheduling import (
    ServiceCreateRequest,
    ServiceCreateResponse,
    ServiceListResponse,
    ServiceLookupResponse,
    ServiceReplaceRequest,
    ServiceReplaceResponse,
)
from app.services.normalization import normalize_public_name
from app.services.scheduling_common import SchedulingDomainError, lock_owner_schedule
from app.services.scheduling_presenters import service_summary

_SERVICE_FIELDS = (
    "public_name",
    "public_description",
    "price_amount",
    "currency",
    "duration_minutes",
    "buffer_before_minutes",
    "buffer_after_minutes",
    "is_active",
    "kind",
    "price_type",
    "price_min_amount",
    "price_max_amount",
    "price_unit",
    "category",
    "sort_order",
    "extra_minutes",
)


def _legacy_price_amount(body: ServiceCreateRequest | ServiceReplaceRequest) -> Decimal:
    if body.price_amount is not None:
        return Decimal(body.price_amount)
    if body.price_min_amount is not None:
        return Decimal(body.price_min_amount)
    return Decimal("0")


def _service_values(body: ServiceCreateRequest | ServiceReplaceRequest) -> dict[str, Any]:
    return {
        "public_name": body.public_name,
        "normalized_public_name": normalize_public_name(body.public_name),
        "public_description": body.public_description,
        "price_amount": _legacy_price_amount(body),
        "currency": body.currency,
        "duration_minutes": body.duration_minutes if body.duration_minutes is not None else 1,
        "buffer_before_minutes": body.buffer_before_minutes,
        "buffer_after_minutes": body.buffer_after_minutes,
        "is_active": body.is_active,
        "kind": body.kind,
        "price_type": body.price_type,
        "price_min_amount": body.price_min_amount,
        "price_max_amount": body.price_max_amount,
        "price_unit": body.price_unit,
        "category": body.category,
        "sort_order": body.sort_order,
        "extra_minutes": body.extra_minutes,
    }


def _ensure_rollback_safe_catalog(body: ServiceCreateRequest | ServiceReplaceRequest) -> None:
    if body.kind == "addon":
        raise SchedulingDomainError("addon_rollout_not_enabled")
    if body.price_type != "fixed":
        raise SchedulingDomainError("price_type_rollout_not_enabled")


def _get_service(
    session: Session,
    identity: RequestIdentity,
    public_name: str,
    *,
    lock: bool = False,
) -> Service | None:
    statement = select(Service).where(
        Service.owner_user_id == identity.user_id,
        Service.normalized_public_name == normalize_public_name(public_name),
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_services(
    session: Session,
    identity: RequestIdentity,
    *,
    include_inactive: bool,
) -> ServiceListResponse:
    statement = select(Service).where(Service.owner_user_id == identity.user_id)
    if not include_inactive:
        statement = statement.where(Service.is_active.is_(True))
    services = session.scalars(
        statement.order_by(
            func.coalesce(Service.category, ""),
            Service.sort_order,
            Service.public_name,
        )
    ).all()
    return ServiceListResponse(services=[service_summary(service) for service in services])


def find_service_exact(
    session: Session,
    identity: RequestIdentity,
    public_name: str,
) -> ServiceLookupResponse:
    service = _get_service(session, identity, public_name)
    if service is None:
        return ServiceLookupResponse(found=False)
    return ServiceLookupResponse(found=True, service=service_summary(service))


def create_service(
    session: Session,
    identity: RequestIdentity,
    body: ServiceCreateRequest,
) -> ServiceCreateResponse:
    _ensure_rollback_safe_catalog(body)
    lock_owner_schedule(session, identity.user_id)
    existing = _get_service(session, identity, body.public_name, lock=True)
    desired = _service_values(body)
    if existing is not None:
        matches = all(getattr(existing, field) == desired[field] for field in _SERVICE_FIELDS)
        if matches:
            return ServiceCreateResponse(service=service_summary(existing), created=False)
        raise SchedulingDomainError("service_name_conflict")

    service = Service(owner_user_id=identity.user_id, **desired)
    session.add(service)
    session.flush()
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="service.created",
            object_type="service",
            object_id=service.id,
            request_id=identity.request_id,
            safe_changes={
                "kind": service.kind,
                "price_type": service.price_type,
                "currency": service.currency,
                "duration_minutes": body.duration_minutes,
                "extra_minutes": service.extra_minutes,
                "buffer_before_minutes": service.buffer_before_minutes,
                "buffer_after_minutes": service.buffer_after_minutes,
                "is_active": service.is_active,
            },
        )
    )
    session.commit()
    return ServiceCreateResponse(service=service_summary(service), created=True)


def replace_service(
    session: Session,
    identity: RequestIdentity,
    body: ServiceReplaceRequest,
) -> ServiceReplaceResponse:
    _ensure_rollback_safe_catalog(body)
    lock_owner_schedule(session, identity.user_id)
    service = _get_service(session, identity, body.current_public_name, lock=True)
    if service is None:
        raise SchedulingDomainError("service_not_found", status_code=404)

    desired = _service_values(body)
    desired_name = desired["normalized_public_name"]
    if desired_name != service.normalized_public_name:
        conflicting = session.scalar(
            select(Service.id)
            .where(
                Service.owner_user_id == identity.user_id,
                Service.normalized_public_name == desired_name,
                Service.id != service.id,
            )
            .limit(1)
        )
        if conflicting is not None:
            raise SchedulingDomainError("service_name_conflict")

    changed_fields: list[str] = []
    for field in (*_SERVICE_FIELDS, "normalized_public_name"):
        value = desired[field]
        if getattr(service, field) != value:
            setattr(service, field, value)
            if field != "normalized_public_name":
                changed_fields.append(field)

    if changed_fields:
        session.add(
            AuditEvent(
                owner_user_id=identity.user_id,
                actor_user_id=identity.user_id,
                action="service.updated",
                object_type="service",
                object_id=service.id,
                request_id=identity.request_id,
                safe_changes={
                    "changed_fields": sorted(changed_fields),
                    "kind": service.kind,
                    "price_type": service.price_type,
                    "currency": service.currency,
                    "duration_minutes": body.duration_minutes,
                    "extra_minutes": service.extra_minutes,
                    "buffer_before_minutes": service.buffer_before_minutes,
                    "buffer_after_minutes": service.buffer_after_minutes,
                    "is_active": service.is_active,
                },
            )
        )
    session.commit()
    return ServiceReplaceResponse(
        service=service_summary(service),
        changed=bool(changed_fields),
        changed_fields=sorted(changed_fields),
    )
