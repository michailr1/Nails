"""Add protected feedback events.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    feedback_kind = postgresql.ENUM(
        "thumbs_down",
        "unrecognized",
        name="feedback_kind",
        create_type=False,
    )
    feedback_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "feedback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", feedback_kind, nullable=False),
        sa.Column("safe_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feedback_events_owner_created_at",
        "feedback_events",
        ["owner_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_feedback_events_created_at",
        "feedback_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_events_created_at", table_name="feedback_events")
    op.drop_index("ix_feedback_events_owner_created_at", table_name="feedback_events")
    op.drop_table("feedback_events")
    postgresql.ENUM(name="feedback_kind").drop(op.get_bind(), checkfirst=True)
