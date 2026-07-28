"""make client booking requests reachable before card resolution

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "booking_requests",
        "client_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.add_column(
        "booking_requests",
        sa.Column("requested_public_name", sa.String(length=160), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE booking_requests AS request "
            "SET requested_public_name = client.public_name "
            "FROM clients AS client "
            "WHERE request.client_id = client.id "
            "AND request.requested_public_name IS NULL"
        )
    )
    op.create_check_constraint(
        "booking_request_approved_has_booking",
        "booking_requests",
        "status <> 'approved' OR booking_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "booking_request_approved_has_booking",
        "booking_requests",
        type_="check",
    )
    op.drop_column("booking_requests", "requested_public_name")
    op.alter_column(
        "booking_requests",
        "client_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
