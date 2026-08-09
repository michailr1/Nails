"""Add typed/idempotent master forward delivery.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "client_contact_forwards",
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            server_default="client_message",
        ),
    )
    op.add_column(
        "client_contact_forwards",
        sa.Column("dedupe_key", sa.String(length=160), nullable=True),
    )
    op.create_check_constraint(
        "ck_client_contact_forwards_kind_valid",
        "client_contact_forwards",
        "kind IN ('client_message', 'booking_request_created')",
    )
    op.create_index(
        "uq_client_contact_forwards_owner_dedupe",
        "client_contact_forwards",
        ["owner_user_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_client_contact_forwards_owner_dedupe",
        table_name="client_contact_forwards",
    )
    op.drop_constraint(
        "ck_client_contact_forwards_kind_valid",
        "client_contact_forwards",
        type_="check",
    )
    op.drop_column("client_contact_forwards", "dedupe_key")
    op.drop_column("client_contact_forwards", "kind")
