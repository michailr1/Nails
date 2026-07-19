"""add booking catalog snapshot fields

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_INSERT_FUNCTION = "nails_fill_legacy_booking_catalog_snapshot"
_LEGACY_INSERT_TRIGGER = "trg_bookings_fill_legacy_catalog_snapshot"


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column(
            "catalog_items_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "catalog_price_type_snapshot",
            sa.String(length=16),
            server_default="fixed",
            nullable=False,
        ),
    )
    op.add_column(
        "bookings",
        sa.Column("catalog_price_min_snapshot", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("catalog_price_max_snapshot", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("catalog_price_unit_snapshot", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "duration_source",
            sa.String(length=32),
            server_default="catalog_snapshot",
            nullable=False,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE bookings AS b
            SET catalog_items_snapshot = jsonb_build_array(
                    jsonb_build_object(
                        'service_id', s.id::text,
                        'kind', 'base',
                        'public_name', s.public_name,
                        'price_type', 'fixed',
                        'price_amount', b.price_amount::text,
                        'price_min_amount', NULL,
                        'price_max_amount', NULL,
                        'price_unit', NULL,
                        'currency', b.currency,
                        'duration_minutes', b.duration_minutes_snapshot,
                        'extra_minutes', 0
                    )
                ),
                catalog_price_type_snapshot = 'fixed',
                catalog_price_min_snapshot = b.price_amount,
                catalog_price_max_snapshot = b.price_amount,
                duration_source = 'catalog_snapshot'
            FROM services AS s
            WHERE s.id = b.service_id
            """
        )
    )

    # The previous application release does not know these columns. During the
    # one-release rollback window it can still insert bookings, so the database
    # must populate the same fixed/base snapshot instead of accepting the [] default.
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {_LEGACY_INSERT_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                service_public_name text;
            BEGIN
                IF NEW.catalog_items_snapshot = '[]'::jsonb THEN
                    SELECT public_name
                    INTO service_public_name
                    FROM services
                    WHERE id = NEW.service_id;

                    IF service_public_name IS NOT NULL THEN
                        NEW.catalog_items_snapshot := jsonb_build_array(
                            jsonb_build_object(
                                'service_id', NEW.service_id::text,
                                'kind', 'base',
                                'public_name', service_public_name,
                                'price_type', 'fixed',
                                'price_amount', NEW.price_amount::text,
                                'price_min_amount', NULL,
                                'price_max_amount', NULL,
                                'price_unit', NULL,
                                'currency', NEW.currency,
                                'duration_minutes', NEW.duration_minutes_snapshot,
                                'extra_minutes', 0
                            )
                        );
                        NEW.catalog_price_type_snapshot := 'fixed';
                        NEW.catalog_price_min_snapshot := NEW.price_amount;
                        NEW.catalog_price_max_snapshot := NEW.price_amount;
                        NEW.catalog_price_unit_snapshot := NULL;
                        NEW.duration_source := 'catalog_snapshot';
                    END IF;
                END IF;

                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_LEGACY_INSERT_TRIGGER}
            BEFORE INSERT ON bookings
            FOR EACH ROW
            EXECUTE FUNCTION {_LEGACY_INSERT_FUNCTION}()
            """
        )
    )

    op.create_check_constraint(
        "booking_catalog_price_type_valid",
        "bookings",
        "catalog_price_type_snapshot IN ('fixed', 'range', 'per_unit', 'on_request')",
    )
    op.create_check_constraint(
        "booking_catalog_price_min_non_negative",
        "bookings",
        "catalog_price_min_snapshot IS NULL OR catalog_price_min_snapshot >= 0",
    )
    op.create_check_constraint(
        "booking_catalog_price_max_non_negative",
        "bookings",
        "catalog_price_max_snapshot IS NULL OR catalog_price_max_snapshot >= 0",
    )
    op.create_check_constraint(
        "booking_catalog_price_range_ordered",
        "bookings",
        "catalog_price_min_snapshot IS NULL OR catalog_price_max_snapshot IS NULL "
        "OR catalog_price_max_snapshot >= catalog_price_min_snapshot",
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP TRIGGER {_LEGACY_INSERT_TRIGGER} ON bookings"))
    op.execute(sa.text(f"DROP FUNCTION {_LEGACY_INSERT_FUNCTION}()"))
    op.drop_constraint("booking_catalog_price_range_ordered", "bookings", type_="check")
    op.drop_constraint("booking_catalog_price_max_non_negative", "bookings", type_="check")
    op.drop_constraint("booking_catalog_price_min_non_negative", "bookings", type_="check")
    op.drop_constraint("booking_catalog_price_type_valid", "bookings", type_="check")
    op.drop_column("bookings", "duration_source")
    op.drop_column("bookings", "catalog_price_unit_snapshot")
    op.drop_column("bookings", "catalog_price_max_snapshot")
    op.drop_column("bookings", "catalog_price_min_snapshot")
    op.drop_column("bookings", "catalog_price_type_snapshot")
    op.drop_column("bookings", "catalog_items_snapshot")
