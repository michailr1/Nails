from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity, RequestIdentity
from app.client_models import (
    BookingRequest,
    BookingRequestStatus,
    ClientTelegramIdentityStatus,
)
from app.models import AuditEvent, Client, User, UserRole
from app.schemas.scheduling_catalog_bookings import CatalogBookingCreateRequest
from app.services.client_contour import ClientBindingContext
from app.services.scheduling_bookings import create_booking
from app.services.scheduling_common import SchedulingDomainError


def _safe_audit(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    action: str,
    request: BookingRequest,
    request_id: str,
    actor_user_id: uuid.UUID | None,
) -> None:
    session.add(
        AuditEvent(
            owner_user_id=owner_user_id,
            actor_user_id=actor_user_id,
            action=action,
            object_type="booking_request",
            object_id=request.id,
            request_id=request_id,
            safe_changes={
                "status": request.status,
                "has_booking": request.booking_id is not None,
            },
        )
    )


def create_client_booking_request(
    session: Session,
    identity: ClientTransportIdentity,
    context: ClientBindingContext,
    *,
    service_name: str,
    addon_names: list[str],
    addon_quantities: dict[str, int],
    starts_at: datetime,
    idempotency_key: str,
) -> BookingRequest:
    binding = context.binding
    if (
        binding.status != ClientTelegramIdentityStatus.active
        or binding.client_id is None
    ):
        raise SchedulingDomainError("client_identity_not_resolved", status_code=409)

    existing = session.scalar(
        select(BookingRequest).where(
            BookingRequest.owner_user_id == context.owner_user_id,
            BookingRequest.binding_id == binding.id,
            BookingRequest.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.client_id != binding.client_id
            or existing.service_name != service_name
            or existing.addon_names != addon_names
            or existing.addon_quantities != addon_quantities
            or existing.starts_at != starts_at
        ):
            raise SchedulingDomainError("idempotency_conflict", status_code=409)
        return existing

    request = BookingRequest(
        owner_user_id=context.owner_user_id,
        binding_id=binding.id,
        client_id=binding.client_id,
        service_name=service_name,
        addon_names=list(addon_names),
        addon_quantities=dict(addon_quantities),
        starts_at=starts_at,
        status=BookingRequestStatus.pending,
        idempotency_key=idempotency_key,
    )
    session.add(request)
    session.flush()
    _safe_audit(
        session,
        owner_user_id=context.owner_user_id,
        action="client_booking_request.created",
        request=request,
        request_id=identity.request_id,
        actor_user_id=None,
    )
    session.commit()
    session.refresh(request)
    return request


def list_client_booking_requests(
    session: Session,
    context: ClientBindingContext,
) -> list[BookingRequest]:
    return list(
        session.scalars(
            select(BookingRequest)
            .where(
                BookingRequest.owner_user_id == context.owner_user_id,
                BookingRequest.binding_id == context.binding.id,
            )
            .order_by(BookingRequest.created_at.desc(), BookingRequest.id.desc())
        ).all()
    )


def cancel_client_booking_request(
    session: Session,
    identity: ClientTransportIdentity,
    context: ClientBindingContext,
    request_id: uuid.UUID,
) -> BookingRequest:
    request = session.scalar(
        select(BookingRequest)
        .where(
            BookingRequest.id == request_id,
            BookingRequest.owner_user_id == context.owner_user_id,
            BookingRequest.binding_id == context.binding.id,
        )
        .with_for_update()
    )
    if request is None:
        raise SchedulingDomainError("booking_request_not_found", status_code=404)
    if request.status == BookingRequestStatus.cancelled:
        return request
    if request.status != BookingRequestStatus.pending:
        raise SchedulingDomainError("booking_request_not_pending", status_code=409)
    request.status = BookingRequestStatus.cancelled
    _safe_audit(
        session,
        owner_user_id=context.owner_user_id,
        action="client_booking_request.cancelled",
        request=request,
        request_id=identity.request_id,
        actor_user_id=None,
    )
    session.commit()
    session.refresh(request)
    return request


def list_master_booking_requests(
    session: Session,
    identity: RequestIdentity,
    *,
    status: str | None = None,
) -> list[BookingRequest]:
    statement = select(BookingRequest).where(
        BookingRequest.owner_user_id == identity.user_id
    )
    if status is not None:
        statement = statement.where(BookingRequest.status == status)
    return list(
        session.scalars(
            statement.order_by(BookingRequest.starts_at, BookingRequest.created_at)
        ).all()
    )


def reject_master_booking_request(
    session: Session,
    identity: RequestIdentity,
    request_id: uuid.UUID,
) -> BookingRequest:
    request = session.scalar(
        select(BookingRequest)
        .where(
            BookingRequest.id == request_id,
            BookingRequest.owner_user_id == identity.user_id,
        )
        .with_for_update()
    )
    if request is None:
        raise SchedulingDomainError("booking_request_not_found", status_code=404)
    if request.status == BookingRequestStatus.rejected:
        return request
    if request.status != BookingRequestStatus.pending:
        raise SchedulingDomainError("booking_request_not_pending", status_code=409)
    request.status = BookingRequestStatus.rejected
    _safe_audit(
        session,
        owner_user_id=identity.user_id,
        action="client_booking_request.rejected",
        request=request,
        request_id=identity.request_id,
        actor_user_id=identity.user_id,
    )
    session.commit()
    session.refresh(request)
    return request


def approve_master_booking_request(
    session: Session,
    identity: RequestIdentity,
    request_id: uuid.UUID,
) -> BookingRequest:
    request = session.scalar(
        select(BookingRequest)
        .where(
            BookingRequest.id == request_id,
            BookingRequest.owner_user_id == identity.user_id,
        )
        .with_for_update()
    )
    if request is None:
        raise SchedulingDomainError("booking_request_not_found", status_code=404)
    if request.status == BookingRequestStatus.approved and request.booking_id is not None:
        return request
    if request.status != BookingRequestStatus.pending:
        raise SchedulingDomainError("booking_request_not_pending", status_code=409)

    client = session.scalar(
        select(Client).where(
            Client.id == request.client_id,
            Client.owner_user_id == identity.user_id,
        )
    )
    owner = session.get(User, identity.user_id)
    if client is None or owner is None or owner.role != UserRole.master or not owner.is_active:
        raise SchedulingDomainError("booking_request_context_invalid", status_code=409)

    booking_body = CatalogBookingCreateRequest(
        client_public_name=client.public_name,
        service_name=request.service_name,
        addon_names=list(request.addon_names),
        addon_quantities=dict(request.addon_quantities),
        starts_at=request.starts_at,
        idempotency_key=f"client-request:{request.id}",
    )
    response = create_booking(session, identity, booking_body)
    request = session.get(BookingRequest, request.id)
    if request is None:
        raise SchedulingDomainError("booking_request_not_found", status_code=404)
    request.booking_id = response.booking.id
    request.status = BookingRequestStatus.approved
    _safe_audit(
        session,
        owner_user_id=identity.user_id,
        action="client_booking_request.approved",
        request=request,
        request_id=identity.request_id,
        actor_user_id=identity.user_id,
    )
    session.commit()
    session.refresh(request)
    return request
