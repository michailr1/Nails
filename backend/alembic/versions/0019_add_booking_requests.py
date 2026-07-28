"""add client booking requests

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "booking_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "binding_id",
            sa.Uuid(),
            sa.ForeignKey("client_telegram_identities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            sa.Uuid(),
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("service_name", sa.String(length=160), nullable=False),
        sa.Column(
            "addon_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "addon_quantities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column(
            "booking_id",
            sa.Uuid(),
            sa.ForeignKey("bookings.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="booking_request_status_valid",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "binding_id",
            "idempotency_key",
            name="uq_booking_requests_binding_idempotency",
        ),
    )
    op.create_index(
        "ix_booking_requests_owner_status_starts",
        "booking_requests",
        ["owner_user_id", "status", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_booking_requests_binding_created",
        "booking_requests",
        ["binding_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_booking_requests_binding_created", table_name="booking_requests")
    op.drop_index("ix_booking_requests_owner_status_starts", table_name="booking_requests")
    op.drop_table("booking_requests")
