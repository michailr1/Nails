"""add booking finalization digest state

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column(
            "finalization_digest_claim_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "finalization_digest_claimed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "finalization_digest_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "bookings",
        sa.Column("finalization_digest_local_day", sa.Date(), nullable=True),
    )
    op.create_check_constraint(
        "booking_finalization_digest_state_consistent",
        "bookings",
        "(finalization_digest_claim_id IS NULL "
        "AND finalization_digest_claimed_at IS NULL "
        "AND finalization_digest_sent_at IS NULL "
        "AND finalization_digest_local_day IS NULL) "
        "OR (finalization_digest_claim_id IS NOT NULL "
        "AND finalization_digest_claimed_at IS NOT NULL "
        "AND finalization_digest_local_day IS NOT NULL)",
    )
    op.create_index(
        "ix_bookings_owner_finalization_digest_day",
        "bookings",
        ["owner_user_id", "finalization_digest_local_day"],
        unique=False,
        postgresql_where=sa.text("finalization_digest_local_day IS NOT NULL"),
    )
    op.create_index(
        "ix_bookings_owner_finalization_digest_claim",
        "bookings",
        ["owner_user_id", "finalization_digest_claim_id"],
        unique=False,
        postgresql_where=sa.text("finalization_digest_claim_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bookings_owner_finalization_digest_claim",
        table_name="bookings",
    )
    op.drop_index(
        "ix_bookings_owner_finalization_digest_day",
        table_name="bookings",
    )
    op.drop_constraint(
        "booking_finalization_digest_state_consistent",
        "bookings",
        type_="check",
    )
    op.drop_column("bookings", "finalization_digest_local_day")
    op.drop_column("bookings", "finalization_digest_sent_at")
    op.drop_column("bookings", "finalization_digest_claimed_at")
    op.drop_column("bookings", "finalization_digest_claim_id")
