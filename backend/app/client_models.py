from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ClientTelegramIdentityStatus(StrEnum):
    pending = "pending"
    active = "active"
    revoked = "revoked"


class BookingRequestStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class ClientTelegramIdentity(Base):
    __tablename__ = "client_telegram_identities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'revoked')",
            name="client_telegram_identity_status_valid",
        ),
        CheckConstraint(
            "(status = 'pending' AND client_id IS NULL "
            "AND requested_public_name IS NOT NULL) "
            "OR (status = 'active' AND client_id IS NOT NULL) "
            "OR status = 'revoked'",
            name="client_telegram_identity_state_consistent",
        ),
        CheckConstraint(
            "bot_reachability IN ('unknown', 'reachable', 'unreachable')",
            name="client_telegram_identity_reachability_valid",
        ),
        UniqueConstraint(
            "owner_user_id",
            "telegram_user_id",
            name="uq_client_telegram_identities_owner_telegram",
        ),
        Index(
            "uq_client_telegram_identities_owner_active_client",
            "owner_user_id",
            "client_id",
            unique=True,
            postgresql_where=text(
                "status = 'active' AND client_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    requested_public_name: Mapped[str | None] = mapped_column(String(160))
    requested_phone: Mapped[str | None] = mapped_column(String(32))
    bot_reachability: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", server_default="unknown"
    )
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BookingRequest(Base):
    __tablename__ = "booking_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="booking_request_status_valid",
        ),
        CheckConstraint(
            "status <> 'approved' OR booking_id IS NOT NULL",
            name="booking_request_approved_has_booking",
        ),
        UniqueConstraint(
            "owner_user_id",
            "binding_id",
            "idempotency_key",
            name="uq_booking_requests_binding_idempotency",
        ),
        Index(
            "uq_booking_requests_source_draft",
            "source_draft_id",
            unique=True,
            postgresql_where=text("source_draft_id IS NOT NULL"),
        ),
        Index(
            "ix_booking_requests_owner_status_starts",
            "owner_user_id",
            "status",
            "starts_at",
        ),
        Index(
            "ix_booking_requests_binding_created",
            "binding_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_telegram_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_booking_drafts.id", ondelete="RESTRICT"),
    )
    requested_public_name: Mapped[str | None] = mapped_column(String(160))
    service_name: Mapped[str] = mapped_column(String(160), nullable=False)
    addon_names: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    addon_quantities: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ClientTelegramContext(Base):
    __tablename__ = "client_telegram_contexts"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    active_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_telegram_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ClientContactForward(Base):
    __tablename__ = "client_contact_forwards"
    __table_args__ = (
        Index(
            "ix_client_contact_forwards_pending",
            "sent_at",
            "claimed_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_telegram_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_public_name: Mapped[str] = mapped_column(String(160), nullable=False)
    message_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MasterPublicProfile(Base):
    __tablename__ = "master_public_profile"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    public_contact: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MasterLinkToken(Base):
    __tablename__ = "master_link_tokens"
    __table_args__ = (
        Index(
            "ix_master_link_tokens_owner_active",
            "owner_user_id",
            "revoked_at",
        ),
    )

    token: Mapped[str] = mapped_column(String(96), primary_key=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
