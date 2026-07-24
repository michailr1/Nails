from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import TimestampMixin


class ClientTelegramIdentityStatus(StrEnum):
    pending = "pending"
    active = "active"
    revoked = "revoked"


class ClientTelegramIdentity(TimestampMixin, Base):
    __tablename__ = "client_telegram_identities"
    __table_args__ = (
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
            postgresql_where=text("status = 'active' AND client_id IS NOT NULL"),
        ),
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
        String(16),
        nullable=False,
        default=ClientTelegramIdentityStatus.pending,
        server_default=ClientTelegramIdentityStatus.pending.value,
    )
    requested_public_name: Mapped[str | None] = mapped_column(String(160))
    requested_phone: Mapped[str | None] = mapped_column(String(32))
