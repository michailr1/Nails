"""extend client cards

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("private_alias", sa.String(length=160), nullable=True))
    op.add_column(
        "clients",
        sa.Column("normalized_private_alias", sa.String(length=160), nullable=True),
    )
    op.add_column("clients", sa.Column("contact_channel", sa.String(length=64), nullable=True))
    op.add_column("clients", sa.Column("birthday", sa.Date(), nullable=True))
    op.add_column("clients", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("clients", sa.Column("nail_skin_notes", sa.Text(), nullable=True))
    op.add_column("clients", sa.Column("sensitivity_notes", sa.Text(), nullable=True))
    op.add_column("clients", sa.Column("style_preferences", sa.Text(), nullable=True))
    op.add_column(
        "clients",
        sa.Column("communication_preferences", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_clients_owner_normalized_private_alias",
        "clients",
        ["owner_user_id", "normalized_private_alias"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_clients_owner_normalized_private_alias", table_name="clients")
    op.drop_column("clients", "communication_preferences")
    op.drop_column("clients", "style_preferences")
    op.drop_column("clients", "sensitivity_notes")
    op.drop_column("clients", "nail_skin_notes")
    op.drop_column("clients", "notes")
    op.drop_column("clients", "birthday")
    op.drop_column("clients", "contact_channel")
    op.drop_column("clients", "normalized_private_alias")
    op.drop_column("clients", "private_alias")
