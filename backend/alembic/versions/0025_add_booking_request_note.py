"""add optional client note to booking drafts and requests

Revision ID: 0025
Revises: 0024
"""

from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_booking_drafts",
        sa.Column("note", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("note", sa.String(length=300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("booking_requests", "note")
    op.drop_column("client_booking_drafts", "note")
