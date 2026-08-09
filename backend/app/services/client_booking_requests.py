from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import ClientTransportIdentity, RequestIdentity
from app.client_models import (
    BookingRequest,
    BookingRequestStatus,
    ClientTelegramIdentity,
    ClientTelegramIdentityStatus,
)
from app.client_notification_models import ClientLinkRecord
from app.models import AuditEvent, Client, ClientProfileStatus, User, UserRole
from app.schemas.client_booking_requests import BookingRequestResolutionValue
from app.schemas.scheduling_catalog_bookings import CatalogBookingCreateRequest
from app.services.client_contact_forward import enqueue_booking_request_master_forward
from app.services.client_contour import ClientBindingContext
from app.services.client_notifications import enqueue_booking_request_notification
from app.services.normalization import normalize_public_name
from app.services.scheduling_bookings import create_booking
from app.services.scheduling_common import SchedulingDomainError
from app.services.scheduling_lookup import get_active_addons, get_active_service

MAX_PENDING_REQUESTS_PER_BINDING = 3


def _safe_audit(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    action: str,
    request: BookingRequest,
    request_id: str,
    actor_user_id: uuid.UUID | None,
    actor_type: str,
    structural_changes: dict[str, bool] | None = None,
) -> None:
    safe_changes: dict[str, object] = {
        "actor_type": actor_type,
        "status": request.status,
        "has_booking": request.booking_id is not None,
    }
    if structural_changes is not None:
        safe_changes["structural_changes"] = structural_changes
    session.add(
        AuditEvent(
            owner_user_id=owner_user_id,
            actor_user_id=actor_user_id,
            action=action,
            object_type="booking_request",
            object_id=request.id,
            request_id=request_id,
            safe_changes=safe_changes,
        )
    )


def _validate_request_catalog(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    service_name: str,
    addon_names: list[str],
) -> None:
    get_active_service(session, owner_user_id, service_name)
    get_active_addons(session, owner_user_id, addon_names)


def _existing_request(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    binding_id: uuid.UUID,
    idempotency_key: str,
    source_draft_id: uuid.UUID | None,
) -> BookingRequest | None:
    if source_draft_id is not None:
        by_draft = session.scalar(
            select(BookingRequest).where(
                BookingRequest.owner_user_id == owner_user_id,
                BookingRequest.binding_id == binding_id,
                BookingRequest.source_draft_id == source_draft_id,
            )
        )
        if by_draft is not None:
            return by_draft
    return session.scalar(
        select(BookingRequest).where(
            BookingRequest.owner_user_id == owner_user_id,
            BookingRequest.binding_id == binding_id,
            BookingRequest.idempotency_key == idempotency_key,
        )
    )


def _lock_binding_request_creation(session: Session, binding_id: uuid.UUID) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 7))"),
        {"key": f"client-pending:{binding_id}"},
    )


def _enforce_pending_limit(session: Session, binding_id: uuid.UUID) -> None:
    pending_count = session.scalar(
        select(func.count(BookingRequest.id)).where(
            BookingRequest.binding_id == binding_id,
            BookingRequest.status == BookingRequestStatus.pending,
        )
    )
    if int(pending_count or 0) >= MAX_PENDING_REQUESTS_PER_BINDING:
        raise SchedulingDomainError(
            "client_pending_request_limit",
            status_code=429,
            details={"limit": MAX_PENDING_REQUESTS_PER_BINDING},
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
    source_draft_id: uuid.UUID | None = None,
) -> BookingRequest:
    binding = context.binding
    if binding.status == ClientTelegramIdentityStatus.revoked:
        raise SchedulingDomainError("client_identity_revoked", status_code=403)
    if binding.status not in (
        ClientTelegramIdentityStatus.pending,
        ClientTelegramIdentityStatus.active,
    ):
        raise SchedulingDomainError("client_identity_invalid", status_code=409)
    if not binding.requested_public_name:
        raise SchedulingDomainError("client_identity_name_missing", status_code=409)
    if starts_at.astimezone(UTC) <= datetime.now(UTC):
        raise SchedulingDomainError("booking_request_start_in_past", status_code=422)

    _validate_request_catalog(
        session,
        owner_user_id=context.owner_user_id,
        service_name=service_name,
        addon_names=addon_names,
    )

    existing = _existing_request(
        session,
        owner_user_id=context.owner_user_id,
        binding_id=binding.id,
        idempotency_key=idempotency_key,
        source_draft_id=source_draft_id,
    )
    if existing is not None:
        if source_draft_id is not None and existing.source_draft_id == source_draft_id:
            return existing
        if (
            existing.service_name != service_name
            or existing.addon_names != addon_names
            or existing.addon_quantities != addon_quantities
            or existing.starts_at.astimezone(UTC) != starts_at.astimezone(UTC)
        ):
            raise SchedulingDomainError("idempotency_conflict", status_code=409)
        return existing

    _lock_binding_request_creation(session, binding.id)
    existing = _existing_request(
        session,
        owner_user_id=context.owner_user_id,
        binding_id=binding.id,
        idempotency_key=idempotency_key,
        source_draft_id=source_draft_id,
    )
    if existing is not None:
        if source_draft_id is not None and existing.source_draft_id == source_draft_id:
            return existing
        if (
            existing.service_name != service_name
            or existing.addon_names != addon_names
            or existing.addon_quantities != addon_quantities
            or existing.starts_at.astimezone(UTC) != starts_at.astimezone(UTC)
        ):
            raise SchedulingDomainError("idempotency_conflict", status_code=409)
        return existing

    _enforce_pending_limit(session, binding.id)
    request = BookingRequest(
        owner_user_id=context.owner_user_id,
        binding_id=binding.id,
        client_id=binding.client_id,
        source_draft_id=source_draft_id,
        requested_public_name=binding.requested_public_name,
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
        actor_type="client_bot",
    )
    enqueue_booking_request_master_forward(session, request)
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
        actor_type="client_bot",
    )
    enqueue_booking_request_notification(session, request, event_type="cancelled")
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
        actor_type="master",
    )
    enqueue_booking_request_notification(session, request, event_type="rejected")
    session.commit()
    session.refresh(request)
    return request


def _get_active_client_by_id(
    session: Session,
    *,
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


def _ensure_client_not_bound_elsewhere(
    session: Session,
    *,
    owner_user_id: uuid.UUID,
    client_id: uuid.UUID,
    binding_id: uuid.UUID,
) -> None:
    occupied = session.scalar(
        select(ClientTelegramIdentity.id).where(
            ClientTelegramIdentity.owner_user_id == owner_user_id,
            ClientTelegramIdentity.client_id == client_id,
            ClientTelegramIdentity.status == ClientTelegramIdentityStatus.active,
            ClientTelegramIdentity.id != binding_id,
        )
    )
    if occupied is not None:
        raise SchedulingDomainError("client_already_linked", status_code=409)


def _record_master_approval_link(
    session: Session,
    *,
    request: BookingRequest,
    binding: ClientTelegramIdentity,
    client: Client,
) -> None:
    existing = session.scalar(
        select(ClientLinkRecord.id).where(
            ClientLinkRecord.owner_user_id == request.owner_user_id,
            ClientLinkRecord.binding_id == binding.id,
            ClientLinkRecord.client_id == client.id,
            ClientLinkRecord.undone_at.is_(None),
        )
    )
    if existing is None:
        session.add(
            ClientLinkRecord(
                owner_user_id=request.owner_user_id,
                binding_id=binding.id,
                client_id=client.id,
                source="master_approval",
            )
        )


def _resolve_client_for_approval(
    session: Session,
    *,
    request: BookingRequest,
    resolution: BookingRequestResolutionValue,
    selected_client_id: uuid.UUID | None,
) -> Client:
    binding = session.scalar(
        select(ClientTelegramIdentity)
        .where(
            ClientTelegramIdentity.id == request.binding_id,
            ClientTelegramIdentity.owner_user_id == request.owner_user_id,
        )
        .with_for_update()
    )
    if binding is None or binding.status == ClientTelegramIdentityStatus.revoked:
        raise SchedulingDomainError("booking_request_context_invalid", status_code=409)

    already_resolved_id = request.client_id or binding.client_id
    if already_resolved_id is not None:
        client = _get_active_client_by_id(
            session,
            owner_user_id=request.owner_user_id,
            client_id=already_resolved_id,
        )
        _ensure_client_not_bound_elsewhere(
            session,
            owner_user_id=request.owner_user_id,
            client_id=client.id,
            binding_id=binding.id,
        )
        request.client_id = client.id
        binding.client_id = client.id
        binding.status = ClientTelegramIdentityStatus.active
        return client

    if resolution == BookingRequestResolutionValue.link_existing:
        if selected_client_id is None:
            raise SchedulingDomainError("client_resolution_required", status_code=422)
        client = _get_active_client_by_id(
            session,
            owner_user_id=request.owner_user_id,
            client_id=selected_client_id,
        )
        _ensure_client_not_bound_elsewhere(
            session,
            owner_user_id=request.owner_user_id,
            client_id=client.id,
            binding_id=binding.id,
        )
    else:
        public_name = (request.requested_public_name or "").strip()
        if not public_name:
            raise SchedulingDomainError("client_identity_name_missing", status_code=409)
        normalized_name = normalize_public_name(public_name)
        same_name = session.scalar(
            select(Client.id).where(
                Client.owner_user_id == request.owner_user_id,
                Client.normalized_public_name == normalized_name,
                Client.profile_status == ClientProfileStatus.active,
            )
        )
        if same_name is not None:
            raise SchedulingDomainError("client_name_conflict", status_code=409)
        client = Client(
            owner_user_id=request.owner_user_id,
            public_name=public_name,
            normalized_public_name=normalized_name,
        )
        session.add(client)
        session.flush()

    request.client_id = client.id
    binding.client_id = client.id
    binding.status = ClientTelegramIdentityStatus.active
    _record_master_approval_link(
        session,
        request=request,
        binding=binding,
        client=client,
    )
    return client


def approve_master_booking_request(
    session: Session,
    identity: RequestIdentity,
    request_id: uuid.UUID,
    *,
    resolution: BookingRequestResolutionValue,
    selected_client_id: uuid.UUID | None,
    service_name: str | None = None,
    addon_names: list[str] | None = None,
    addon_quantities: dict[str, int] | None = None,
    starts_at: datetime | None = None,
    price_override_amount: Decimal | None = None,
    duration_override_minutes: int | None = None,
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
    if (
        request.status == BookingRequestStatus.approved
        and request.booking_id is not None
    ):
        return request
    if request.status != BookingRequestStatus.pending:
        raise SchedulingDomainError("booking_request_not_pending", status_code=409)

    owner = session.get(User, identity.user_id)
    if owner is None or owner.role != UserRole.master or not owner.is_active:
        raise SchedulingDomainError("booking_request_context_invalid", status_code=409)

    final_service_name = service_name or request.service_name
    final_addon_names = list(request.addon_names if addon_names is None else addon_names)
    final_addon_quantities = dict(
        request.addon_quantities if addon_quantities is None else addon_quantities
    )
    final_starts_at = starts_at or request.starts_at
    structural_changes = {
        "service_changed": final_service_name != request.service_name,
        "addons_changed": (
            final_addon_names != list(request.addon_names)
            or final_addon_quantities != dict(request.addon_quantities)
        ),
        "time_changed": (
            final_starts_at.astimezone(UTC) != request.starts_at.astimezone(UTC)
        ),
        "price_overridden": price_override_amount is not None,
        "duration_overridden": duration_override_minutes is not None,
    }
    _validate_request_catalog(
        session,
        owner_user_id=identity.user_id,
        service_name=final_service_name,
        addon_names=final_addon_names,
    )

    client = _resolve_client_for_approval(
        session,
        request=request,
        resolution=resolution,
        selected_client_id=selected_client_id,
    )

    booking_body = CatalogBookingCreateRequest(
        client_public_name=client.public_name,
        service_name=final_service_name,
        addon_names=final_addon_names,
        addon_quantities=final_addon_quantities,
        starts_at=final_starts_at,
        price_override_amount=price_override_amount,
        duration_override_minutes=duration_override_minutes,
        idempotency_key=f"client-request:{request.id}",
    )
    response = create_booking(session, identity, booking_body)
    request = session.get(BookingRequest, request.id)
    if request is None:
        raise SchedulingDomainError("booking_request_not_found", status_code=404)
    request.client_id = client.id
    request.service_name = final_service_name
    request.addon_names = final_addon_names
    request.addon_quantities = final_addon_quantities
    request.starts_at = final_starts_at
    request.booking_id = response.booking.id
    request.status = BookingRequestStatus.approved
    _safe_audit(
        session,
        owner_user_id=identity.user_id,
        action="client_booking_request.approved",
        request=request,
        request_id=identity.request_id,
        actor_user_id=identity.user_id,
        actor_type="master",
        structural_changes=structural_changes,
    )
    enqueue_booking_request_notification(session, request, event_type="approved")
    session.commit()
    session.refresh(request)
    return request
