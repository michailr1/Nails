"""Add persistent master communication preferences.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "master_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("preferred_name", sa.String(length=160), nullable=True),
        sa.Column("assistant_style", sa.String(length=32), nullable=True),
        sa.Column("assistant_style_details", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "assistant_style IS NULL OR assistant_style IN "
            "('business', 'friendly', 'casual', 'playful', 'custom')",
            name="master_preferences_style_valid",
        ),
        sa.CheckConstraint(
            "assistant_style <> 'custom' OR assistant_style_details IS NOT NULL",
            name="master_preferences_custom_details_present",
        ),
    )


def downgrade() -> None:
    op.drop_table("master_preferences")
