"""add web session target owner

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "web_sessions",
        sa.Column(
            "target_owner_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_web_sessions_target_owner_user_id_users",
        "web_sessions",
        "users",
        ["target_owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_web_sessions_target_owner",
        "web_sessions",
        ["target_owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_web_sessions_target_owner", table_name="web_sessions")
    op.drop_constraint(
        "fk_web_sessions_target_owner_user_id_users",
        "web_sessions",
        type_="foreignkey",
    )
    op.drop_column("web_sessions", "target_owner_user_id")
