"""Preserve confirmed onboarding revisions separately from editable drafts.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "onboarding_drafts",
        sa.Column("confirmed_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "onboarding_drafts",
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "onboarding_drafts",
        sa.Column("confirmed_revision", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE onboarding_drafts
        SET confirmed_payload = payload,
            confirmed_revision = 1
        WHERE is_confirmed = true
        """
    )

    op.create_check_constraint(
        op.f("ck_onboarding_drafts_revision_positive"),
        "onboarding_drafts",
        "revision >= 1",
    )
    op.create_check_constraint(
        op.f("ck_onboarding_drafts_confirmed_revision_positive"),
        "onboarding_drafts",
        "confirmed_revision IS NULL OR confirmed_revision >= 1",
    )
    op.create_check_constraint(
        op.f("ck_onboarding_drafts_confirmed_revision_not_ahead"),
        "onboarding_drafts",
        "confirmed_revision IS NULL OR confirmed_revision <= revision",
    )
    op.create_check_constraint(
        op.f("ck_onboarding_drafts_current_confirmation_consistent"),
        "onboarding_drafts",
        "(is_confirmed = false) OR "
        "(confirmed_revision = revision AND confirmed_payload IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_onboarding_drafts_current_confirmation_consistent"),
        "onboarding_drafts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_onboarding_drafts_confirmed_revision_not_ahead"),
        "onboarding_drafts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_onboarding_drafts_confirmed_revision_positive"),
        "onboarding_drafts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_onboarding_drafts_revision_positive"),
        "onboarding_drafts",
        type_="check",
    )
    op.drop_column("onboarding_drafts", "confirmed_revision")
    op.drop_column("onboarding_drafts", "revision")
    op.drop_column("onboarding_drafts", "confirmed_payload")
