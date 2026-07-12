from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserRole(StrEnum):
    admin = "admin"
    master = "master"


class ClientProfileStatus(StrEnum):
    active = "active"
    archived = "archived"


class BookingStatus(StrEnum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


class OnboardingStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    paused = "paused"
    completed = "completed"


class OnboardingSection(StrEnum):
    schedule = "schedule"
    services = "services"
    buffers = "buffers"
    bookings = "bookings"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.master
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    onboarding_state: Mapped[OnboardingState | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class Service(TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "public_name", name="uq_services_owner_public_name"),
        CheckConstraint("price_amount >= 0", name="price_non_negative"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("buffer_before_minutes >= 0", name="buffer_before_non_negative"),
        CheckConstraint("buffer_after_minutes >= 0", name="buffer_after_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    public_name: Mapped[str] = mapped_column(String(160), nullable=False)
    public_description: Mapped[str | None] = mapped_column(Text)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_before_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buffer_after_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Client(TimestampMixin, Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index("ix_clients_owner_normalized_name", "owner_user_id", "normalized_public_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    public_name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_public_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    profile_status: Mapped[ClientProfileStatus] = mapped_column(
        Enum(ClientProfileStatus, name="client_profile_status"),
        nullable=False,
        default=ClientProfileStatus.active,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="end_after_start"),
        CheckConstraint("price_amount >= 0", name="price_non_negative"),
        Index("ix_bookings_starts_at", "starts_at"),
        Index("ix_bookings_owner_starts_at", "owner_user_id", "starts_at"),
        Index("ix_bookings_client_id_starts_at", "client_id", "starts_at"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_bookings_owner_idempotency_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        nullable=False,
        default=BookingStatus.scheduled,
    )
    price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_source: Mapped[str] = mapped_column(String(64), nullable=False)
    price_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)


class ScheduleRule(TimestampMixin, Base):
    __tablename__ = "schedule_rules"
    __table_args__ = (
        Index("ix_schedule_rules_owner_weekday", "owner_user_id", "weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint(
            "(is_working = false) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)",
            name="working_interval_valid",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="valid_date_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    end_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    is_working: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)


class ScheduleException(TimestampMixin, Base):
    __tablename__ = "schedule_exceptions"
    __table_args__ = (
        CheckConstraint(
            "(is_working = false) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)",
            name="working_interval_valid",
        ),
        Index("ix_schedule_exceptions_owner_day", "owner_user_id", "day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    end_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    is_working: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_owner_created_at", "owner_user_id", "created_at"),
        Index("ix_audit_events_object", "object_type", "object_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_id: Mapped[str | None] = mapped_column(String(128))
    safe_changes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OnboardingState(TimestampMixin, Base):
    __tablename__ = "onboarding_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[OnboardingStatus] = mapped_column(
        Enum(OnboardingStatus, name="onboarding_status"),
        nullable=False,
        default=OnboardingStatus.not_started,
    )
    current_step: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="onboarding_state")
    drafts: Mapped[list[OnboardingDraft]] = relationship(
        back_populates="onboarding_state", cascade="all, delete-orphan"
    )


class OnboardingDraft(TimestampMixin, Base):
    __tablename__ = "onboarding_drafts"
    __table_args__ = (
        UniqueConstraint("onboarding_state_id", "section", name="uq_onboarding_draft_section"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "confirmed_revision IS NULL OR confirmed_revision >= 1",
            name="confirmed_revision_positive",
        ),
        CheckConstraint(
            "confirmed_revision IS NULL OR confirmed_revision <= revision",
            name="confirmed_revision_not_ahead",
        ),
        CheckConstraint(
            "(is_confirmed = false) OR "
            "(confirmed_revision = revision AND confirmed_payload IS NOT NULL)",
            name="current_confirmation_consistent",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    onboarding_state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_states.id", ondelete="CASCADE"),
        nullable=False,
    )
    section: Mapped[OnboardingSection] = mapped_column(
        Enum(OnboardingSection, name="onboarding_section"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    confirmed_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    confirmed_revision: Mapped[int | None] = mapped_column(Integer)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    onboarding_state: Mapped[OnboardingState] = relationship(back_populates="drafts")
