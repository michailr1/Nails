"""Add client notification outbox, linking records, and draft submit state.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_booking_drafts",
        sa.Column("submitted_request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "client_booking_drafts",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_client_booking_drafts_submitted_request",
        "client_booking_drafts",
        "booking_requests",
        ["submitted_request_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "client_booking_draft_submission_consistent",
        "client_booking_drafts",
        "(submitted_request_id IS NULL AND submitted_at IS NULL) OR "
        "(submitted_request_id IS NOT NULL AND submitted_at IS NOT NULL)",
    )

    op.add_column(
        "client_telegram_identities",
        sa.Column(
            "bot_reachability",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "client_telegram_identities",
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "client_telegram_identity_reachability_valid",
        "client_telegram_identities",
        "bot_reachability IN ('unknown', 'reachable', 'unreachable')",
    )

    op.create_table(
        "client_notification_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('approved', 'rejected', 'cancelled')",
            name="client_notification_event_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'sent', 'failed')",
            name="client_notification_status_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="client_notification_attempts_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["client_telegram_identities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["booking_request_id"], ["booking_requests.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "binding_id",
            "idempotency_key",
            name="uq_client_notification_outbox_idempotency",
        ),
    )
    op.create_index(
        "ix_client_notification_outbox_delivery",
        "client_notification_outbox",
        ["status", "next_attempt_at", "claimed_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_client_notification_outbox_binding_created",
        "client_notification_outbox",
        ["binding_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "client_personal_link_tokens",
        sa.Column("token", sa.String(length=96), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_binding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["consumed_binding_id"],
            ["client_telegram_identities.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        "ix_client_personal_link_owner_client_active",
        "client_personal_link_tokens",
        ["owner_user_id", "client_id", "revoked_at", "consumed_at", "expires_at"],
        unique=False,
    )

    op.create_table(
        "client_link_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source IN ('confirmed_contact', 'personal_link', 'master_approval')",
            name="client_link_record_source_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["client_telegram_identities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_client_link_records_owner_created",
        "client_link_records",
        ["owner_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_client_link_records_binding_created",
        "client_link_records",
        ["binding_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_client_link_records_binding_created", table_name="client_link_records")
    op.drop_index("ix_client_link_records_owner_created", table_name="client_link_records")
    op.drop_table("client_link_records")
    op.drop_index(
        "ix_client_personal_link_owner_client_active",
        table_name="client_personal_link_tokens",
    )
    op.drop_table("client_personal_link_tokens")
    op.drop_index(
        "ix_client_notification_outbox_binding_created",
        table_name="client_notification_outbox",
    )
    op.drop_index(
        "ix_client_notification_outbox_delivery",
        table_name="client_notification_outbox",
    )
    op.drop_table("client_notification_outbox")
    op.drop_constraint(
        "client_telegram_identity_reachability_valid",
        "client_telegram_identities",
        type_="check",
    )
    op.drop_column("client_telegram_identities", "last_delivery_at")
    op.drop_column("client_telegram_identities", "bot_reachability")
    op.drop_constraint(
        "client_booking_draft_submission_consistent",
        "client_booking_drafts",
        type_="check",
    )
    op.drop_constraint(
        "fk_client_booking_drafts_submitted_request",
        "client_booking_drafts",
        type_="foreignkey",
    )
    op.drop_column("client_booking_drafts", "submitted_at")
    op.drop_column("client_booking_drafts", "submitted_request_id")
