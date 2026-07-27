"""add client contact forwards

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_contact_forwards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "binding_id",
            sa.Uuid(),
            sa.ForeignKey("client_telegram_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_public_name", sa.String(length=160), nullable=False),
        sa.Column("message_text", sa.String(length=2000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_client_contact_forwards_pending",
        "client_contact_forwards",
        ["sent_at", "claimed_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_contact_forwards_pending",
        table_name="client_contact_forwards",
    )
    op.drop_table("client_contact_forwards")
