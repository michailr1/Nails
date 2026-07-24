from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.db import Base


class WebChallengeStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    consumed = "consumed"
    expired = "expired"
    locked = "locked"
    denied = "denied"


class WebLoginChallenge(Base):
    __tablename__ = "web_login_challenges"
    __table_args__ = (
        Index("ix_web_login_challenges_status_expires", "status", "expires_at"),
        Index("ix_web_login_challenges_ip_created", "request_ip_hash", "created_at"),
        Index(
            "uq_web_login_challenges_pending_scope",
            "pending_scope_hash",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    verification_number_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    code_hash = synonym("verification_number_hash")
    browser_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    pending_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    request_ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebSession(Base):
    __tablename__ = "web_sessions"
    __table_args__ = (
        Index("ix_web_sessions_user_active", "user_id", "revoked_at"),
        Index("ix_web_sessions_expiry", "idle_expires_at", "absolute_expires_at"),
        Index("ix_web_sessions_target_owner", "target_owner_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotation_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)


class WebAuthRateBucket(Base):
    __tablename__ = "web_auth_rate_buckets"
    __table_args__ = (
        UniqueConstraint(
            "action",
            "scope_hash",
            name="uq_web_auth_rate_bucket_scope",
        ),
        Index("ix_web_auth_rate_buckets_window", "window_started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
