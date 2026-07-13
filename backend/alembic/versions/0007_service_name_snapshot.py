"""Preserve the booked service name when services are renamed.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("service_name_snapshot", sa.String(length=160), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE bookings "
            "SET service_name_snapshot = services.public_name "
            "FROM services "
            "WHERE bookings.service_id = services.id"
        )
    )
    op.alter_column(
        "bookings",
        "service_name_snapshot",
        existing_type=sa.String(length=160),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("bookings", "service_name_snapshot")
