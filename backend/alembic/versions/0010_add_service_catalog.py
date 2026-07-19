"""add ADR-007 service catalog fields

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Expand-only migration: legacy columns stay intact so the previous release
    # can still run during rollback. Existing rows become fixed-price base items.
    op.add_column(
        "services",
        sa.Column("kind", sa.String(length=16), server_default="base", nullable=False),
    )
    op.add_column(
        "services",
        sa.Column("price_type", sa.String(length=16), server_default="fixed", nullable=False),
    )
    op.add_column("services", sa.Column("price_min_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("services", sa.Column("price_max_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("services", sa.Column("price_unit", sa.String(length=80), nullable=True))
    op.add_column("services", sa.Column("category", sa.String(length=160), nullable=True))
    op.add_column(
        "services",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "services",
        sa.Column("extra_minutes", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_check_constraint(
        "service_kind_valid",
        "services",
        "kind IN ('base', 'addon')",
    )
    op.create_check_constraint(
        "service_price_type_valid",
        "services",
        "price_type IN ('fixed', 'range', 'per_unit', 'on_request')",
    )
    op.create_check_constraint(
        "service_sort_order_non_negative",
        "services",
        "sort_order >= 0",
    )
    op.create_check_constraint(
        "service_extra_minutes_non_negative",
        "services",
        "extra_minutes >= 0",
    )
    op.create_check_constraint(
        "service_price_min_non_negative",
        "services",
        "price_min_amount IS NULL OR price_min_amount >= 0",
    )
    op.create_check_constraint(
        "service_price_max_non_negative",
        "services",
        "price_max_amount IS NULL OR price_max_amount >= 0",
    )
    op.create_check_constraint(
        "service_price_range_ordered",
        "services",
        "price_min_amount IS NULL OR price_max_amount IS NULL OR price_max_amount >= price_min_amount",
    )
    op.create_index(
        "ix_services_owner_catalog_order",
        "services",
        ["owner_user_id", "category", "sort_order", "public_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_services_owner_catalog_order", table_name="services")
    op.drop_constraint("service_price_range_ordered", "services", type_="check")
    op.drop_constraint("service_price_max_non_negative", "services", type_="check")
    op.drop_constraint("service_price_min_non_negative", "services", type_="check")
    op.drop_constraint("service_extra_minutes_non_negative", "services", type_="check")
    op.drop_constraint("service_sort_order_non_negative", "services", type_="check")
    op.drop_constraint("service_price_type_valid", "services", type_="check")
    op.drop_constraint("service_kind_valid", "services", type_="check")
    op.drop_column("services", "extra_minutes")
    op.drop_column("services", "sort_order")
    op.drop_column("services", "category")
    op.drop_column("services", "price_unit")
    op.drop_column("services", "price_max_amount")
    op.drop_column("services", "price_min_amount")
    op.drop_column("services", "price_type")
    op.drop_column("services", "kind")
