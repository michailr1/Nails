"""Add reusable default work hours to master preferences.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "master_preferences",
        sa.Column(
            "default_work_intervals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_master_preferences_default_work_intervals_array",
        "master_preferences",
        "default_work_intervals IS NULL OR "
        "jsonb_typeof(default_work_intervals) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_master_preferences_default_work_intervals_array",
        "master_preferences",
        type_="check",
    )
    op.drop_column("master_preferences", "default_work_intervals")
