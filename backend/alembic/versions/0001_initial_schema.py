"""Create the initial Nails business schema.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("admin", "master", name="user_role", create_type=False)
client_profile_status = postgresql.ENUM("active", "archived", name="client_profile_status", create_type=False)
booking_status = postgresql.ENUM("scheduled", "completed", "cancelled", "no_show", name="booking_status", create_type=False)
onboarding_status = postgresql.ENUM(
    "not_started", "in_progress", "paused", "completed", name="onboarding_status", create_type=False
)
onboarding_section = postgresql.ENUM("schedule", "services", "buffers", "bookings", name="onboarding_section", create_type=False)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    client_profile_status.create(bind, checkfirst=True)
    booking_status.create(bind, checkfirst=True)
    onboarding_status.create(bind, checkfirst=True)
    onboarding_section.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_user_id", name=op.f("uq_users_telegram_user_id")),
    )

    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_name", sa.String(length=160), nullable=False),
        sa.Column("public_description", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_before_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_after_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("price_amount >= 0", name=op.f("ck_services_price_non_negative")),
        sa.CheckConstraint("duration_minutes > 0", name=op.f("ck_services_duration_positive")),
        sa.CheckConstraint("buffer_before_minutes >= 0", name=op.f("ck_services_buffer_before_non_negative")),
        sa.CheckConstraint("buffer_after_minutes >= 0", name=op.f("ck_services_buffer_after_non_negative")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_services_owner_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("owner_user_id", "public_name", name="uq_services_owner_public_name"),
    )

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_name", sa.String(length=160), nullable=False),
        sa.Column("normalized_public_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("profile_status", client_profile_status, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_clients_owner_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
    )
    op.create_index(
        "ix_clients_owner_normalized_name",
        "clients",
        ["owner_user_id", "normalized_public_name"],
    )

    op.create_table(
        "schedule_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("is_working", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        *timestamps(),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_schedule_rules_weekday_range")),
        sa.CheckConstraint("(is_working = false) OR (start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)", name=op.f("ck_schedule_rules_working_interval_valid")),
        sa.CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name=op.f("ck_schedule_rules_valid_date_range")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_schedule_rules_owner_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_rules")),
    )
    op.create_index(
        "ix_schedule_rules_owner_weekday",
        "schedule_rules",
        ["owner_user_id", "weekday"],
    )

    op.create_table(
        "schedule_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("is_working", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        *timestamps(),
        sa.CheckConstraint("(is_working = false) OR (start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)", name=op.f("ck_schedule_exceptions_working_interval_valid")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_schedule_exceptions_owner_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_exceptions")),
    )
    op.create_index(
        "ix_schedule_exceptions_owner_day",
        "schedule_exceptions",
        ["owner_user_id", "day"],
    )

    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", booking_status, nullable=False),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price_source", sa.String(length=64), nullable=False),
        sa.Column("price_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        *timestamps(),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_bookings_end_after_start")),
        sa.CheckConstraint("price_amount >= 0", name=op.f("ck_bookings_price_non_negative")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_bookings_owner_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name=op.f("fk_bookings_client_id_clients"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], name=op.f("fk_bookings_service_id_services"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_bookings_idempotency_key")),
    )
    op.create_index("ix_bookings_starts_at", "bookings", ["starts_at"])
    op.create_index(
        "ix_bookings_owner_starts_at", "bookings", ["owner_user_id", "starts_at"]
    )
    op.create_index("ix_bookings_client_id_starts_at", "bookings", ["client_id", "starts_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("object_type", sa.String(length=100), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("safe_changes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_audit_events_owner_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_audit_events_actor_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_owner_created_at",
        "audit_events",
        ["owner_user_id", "created_at"],
    )
    op.create_index("ix_audit_events_object", "audit_events", ["object_type", "object_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "onboarding_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", onboarding_status, nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_onboarding_states_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboarding_states")),
        sa.UniqueConstraint("user_id", name=op.f("uq_onboarding_states_user_id")),
    )

    op.create_table(
        "onboarding_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("onboarding_state_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", onboarding_section, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["onboarding_state_id"], ["onboarding_states.id"], name=op.f("fk_onboarding_drafts_onboarding_state_id_onboarding_states"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboarding_drafts")),
        sa.UniqueConstraint("onboarding_state_id", "section", name="uq_onboarding_draft_section"),
    )


def downgrade() -> None:
    op.drop_table("onboarding_drafts")
    op.drop_table("onboarding_states")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_object", table_name="audit_events")
    op.drop_index("ix_audit_events_owner_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_bookings_client_id_starts_at", table_name="bookings")
    op.drop_index("ix_bookings_owner_starts_at", table_name="bookings")
    op.drop_index("ix_bookings_starts_at", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_schedule_exceptions_owner_day", table_name="schedule_exceptions")
    op.drop_table("schedule_exceptions")
    op.drop_index("ix_schedule_rules_owner_weekday", table_name="schedule_rules")
    op.drop_table("schedule_rules")
    op.drop_index("ix_clients_owner_normalized_name", table_name="clients")
    op.drop_table("clients")
    op.drop_table("services")
    op.drop_table("users")

    bind = op.get_bind()
    onboarding_section.drop(bind, checkfirst=True)
    onboarding_status.drop(bind, checkfirst=True)
    booking_status.drop(bind, checkfirst=True)
    client_profile_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
