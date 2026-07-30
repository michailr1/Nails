from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ClientNotificationOutbox(Base):
    __tablename__ = "client_notification_outbox"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('approved', 'rejected', 'cancelled')",
            name="client_notification_event_type_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'claimed', 'sent', 'failed')",
            name="client_notification_status_valid",
        ),
        CheckConstraint("attempts >= 0", name="client_notification_attempts_non_negative"),
        UniqueConstraint(
            "owner_user_id",
            "binding_id",
            "idempotency_key",
            name="uq_client_notification_outbox_idempotency",
        ),
        Index(
            "ix_client_notification_outbox_delivery",
            "status",
            "next_attempt_at",
            "claimed_at",
            "created_at",
        ),
        Index(
            "ix_client_notification_outbox_binding_created",
            "binding_id",
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
    booking_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking_requests.id", ondelete="SET NULL"),
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ClientPersonalLinkToken(Base):
    __tablename__ = "client_personal_link_tokens"
    __table_args__ = (
        Index(
            "ix_client_personal_link_owner_client_active",
            "owner_user_id",
            "client_id",
            "revoked_at",
            "consumed_at",
            "expires_at",
        ),
    )

    token: Mapped[str] = mapped_column(String(96), primary_key=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_binding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_telegram_identities.id", ondelete="SET NULL"),
    )


class ClientLinkRecord(Base):
    __tablename__ = "client_link_records"
    __table_args__ = (
        CheckConstraint(
            "source IN ('confirmed_contact', 'personal_link', 'master_approval')",
            name="client_link_record_source_valid",
        ),
        Index("ix_client_link_records_owner_created", "owner_user_id", "created_at"),
        Index("ix_client_link_records_binding_created", "binding_id", "created_at"),
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
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
