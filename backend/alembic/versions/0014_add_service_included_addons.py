"""add owner-scoped included addon links

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-23
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
    op.create_unique_constraint(
        "uq_services_owner_id",
        "services",
        ["owner_user_id", "id"],
    )
    op.create_table(
        "service_included_addons",
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "base_service_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "addon_service_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "base_service_id <> addon_service_id",
            name="service_included_addon_distinct",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "base_service_id"],
            ["services.owner_user_id", "services.id"],
            ondelete="CASCADE",
            name="fk_service_included_addons_owner_base",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "addon_service_id"],
            ["services.owner_user_id", "services.id"],
            ondelete="CASCADE",
            name="fk_service_included_addons_owner_addon",
        ),
        sa.PrimaryKeyConstraint(
            "owner_user_id",
            "base_service_id",
            "addon_service_id",
            name="pk_service_included_addons",
        ),
    )
    op.create_index(
        "ix_service_included_addons_owner_base",
        "service_included_addons",
        ["owner_user_id", "base_service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_service_included_addons_owner_base",
        table_name="service_included_addons",
    )
    op.drop_table("service_included_addons")
    op.drop_constraint("uq_services_owner_id", "services", type_="unique")
