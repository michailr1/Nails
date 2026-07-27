"""add client telegram contexts

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_telegram_contexts",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "active_binding_id",
            sa.Uuid(),
            sa.ForeignKey("client_telegram_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("client_telegram_contexts")
