"""activate catalog composition with rollback guard

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_INSERT_FUNCTION = "nails_fill_legacy_booking_catalog_snapshot"


def upgrade() -> None:
    # The previous application release can run against this expanded schema during
    # rollback. It only understands one fixed base service. Reject unsafe inserts
    # from that release while allowing the catalog-v2 path to persist composition.
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_LEGACY_INSERT_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                service_public_name text;
                service_kind text;
                service_price_type text;
            BEGIN
                SELECT public_name, kind, price_type
                INTO service_public_name, service_kind, service_price_type
                FROM services
                WHERE id = NEW.service_id;

                IF NEW.duration_source = 'catalog_snapshot'
                   AND (service_kind <> 'base' OR service_price_type <> 'fixed') THEN
                    RAISE EXCEPTION 'legacy booking path cannot persist activated catalog item'
                        USING ERRCODE = '23514';
                END IF;

                IF NEW.catalog_items_snapshot = '[]'::jsonb
                   AND service_public_name IS NOT NULL THEN
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

                RETURN NEW;
            END;
            $$
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_LEGACY_INSERT_FUNCTION}()
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
