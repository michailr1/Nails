"""Add normalized service lookup and immutable booking reservation snapshots.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("normalized_public_name", sa.String(length=160), nullable=True),
    )
    op.execute(
        """
        UPDATE services
           SET normalized_public_name = lower(
               regexp_replace(trim(public_name), '\\s+', ' ', 'g')
           )
        """
    )
    op.execute(
        """
        CREATE FUNCTION nails_normalize_service_public_name()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            NEW.normalized_public_name := lower(
                regexp_replace(trim(NEW.public_name), '\\s+', ' ', 'g')
            );
            RETURN NEW;
        END
        $function$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_services_normalized_public_name
        BEFORE INSERT OR UPDATE OF public_name
        ON services
        FOR EACH ROW
        EXECUTE FUNCTION nails_normalize_service_public_name()
        """
    )
    op.alter_column("services", "normalized_public_name", nullable=False)
    op.create_index(
        "uq_services_owner_normalized_public_name",
        "services",
        ["owner_user_id", "normalized_public_name"],
        unique=True,
    )

    op.create_index(
        "uq_clients_owner_active_normalized_name",
        "clients",
        ["owner_user_id", "normalized_public_name"],
        unique=True,
        postgresql_where=sa.text("profile_status = 'active'::client_profile_status"),
    )

    op.add_column(
        "bookings",
        sa.Column("duration_minutes_snapshot", sa.Integer(), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("buffer_before_minutes_snapshot", sa.Integer(), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("buffer_after_minutes_snapshot", sa.Integer(), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("reserved_starts_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("reserved_ends_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE bookings AS booking
           SET duration_minutes_snapshot = GREATEST(
                   1,
                   round(
                       extract(epoch FROM (booking.ends_at - booking.starts_at)) / 60.0
                   )::integer
               ),
               buffer_before_minutes_snapshot = service.buffer_before_minutes,
               buffer_after_minutes_snapshot = service.buffer_after_minutes,
               reserved_starts_at = booking.starts_at
                   - make_interval(mins => service.buffer_before_minutes),
               reserved_ends_at = booking.ends_at
                   + make_interval(mins => service.buffer_after_minutes)
          FROM services AS service
         WHERE service.id = booking.service_id
        """
    )

    op.execute(
        """
        CREATE FUNCTION nails_prepare_booking_reservation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        DECLARE
            service_duration integer;
            service_before integer;
            service_after integer;
        BEGIN
            PERFORM pg_advisory_xact_lock(
                hashtextextended(NEW.owner_user_id::text, 0)
            );

            IF NEW.duration_minutes_snapshot IS NULL
               OR NEW.buffer_before_minutes_snapshot IS NULL
               OR NEW.buffer_after_minutes_snapshot IS NULL THEN
                SELECT duration_minutes,
                       buffer_before_minutes,
                       buffer_after_minutes
                  INTO service_duration,
                       service_before,
                       service_after
                  FROM services
                 WHERE id = NEW.service_id
                   AND owner_user_id = NEW.owner_user_id;

                IF NOT FOUND THEN
                    RAISE EXCEPTION 'booking service owner mismatch'
                        USING ERRCODE = '23503';
                END IF;

                NEW.duration_minutes_snapshot := COALESCE(
                    NEW.duration_minutes_snapshot,
                    service_duration
                );
                NEW.buffer_before_minutes_snapshot := COALESCE(
                    NEW.buffer_before_minutes_snapshot,
                    service_before
                );
                NEW.buffer_after_minutes_snapshot := COALESCE(
                    NEW.buffer_after_minutes_snapshot,
                    service_after
                );
            END IF;

            NEW.ends_at := COALESCE(
                NEW.ends_at,
                NEW.starts_at
                    + make_interval(mins => NEW.duration_minutes_snapshot)
            );
            NEW.expected_ends_at := COALESCE(
                NEW.expected_ends_at,
                NEW.ends_at
            );
            NEW.reserved_starts_at := COALESCE(
                NEW.reserved_starts_at,
                NEW.starts_at
                    - make_interval(mins => NEW.buffer_before_minutes_snapshot)
            );
            NEW.reserved_ends_at := COALESCE(
                NEW.reserved_ends_at,
                NEW.ends_at
                    + make_interval(mins => NEW.buffer_after_minutes_snapshot)
            );

            IF NEW.status = 'scheduled'::booking_status
               AND EXISTS (
                   SELECT 1
                     FROM bookings AS existing
                    WHERE existing.owner_user_id = NEW.owner_user_id
                      AND existing.status = 'scheduled'::booking_status
                      AND existing.id <> NEW.id
                      AND existing.reserved_starts_at < NEW.reserved_ends_at
                      AND existing.reserved_ends_at > NEW.reserved_starts_at
               ) THEN
                RAISE EXCEPTION 'booking_overlap'
                    USING ERRCODE = '23P01';
            END IF;

            RETURN NEW;
        END
        $function$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bookings_prepare_reservation
        BEFORE INSERT OR UPDATE
        ON bookings
        FOR EACH ROW
        EXECUTE FUNCTION nails_prepare_booking_reservation()
        """
    )

    op.alter_column("bookings", "duration_minutes_snapshot", nullable=False)
    op.alter_column("bookings", "buffer_before_minutes_snapshot", nullable=False)
    op.alter_column("bookings", "buffer_after_minutes_snapshot", nullable=False)
    op.alter_column("bookings", "reserved_starts_at", nullable=False)
    op.alter_column("bookings", "reserved_ends_at", nullable=False)

    op.create_check_constraint(
        "duration_snapshot_positive",
        "bookings",
        "duration_minutes_snapshot > 0",
    )
    op.create_check_constraint(
        "buffer_before_snapshot_non_negative",
        "bookings",
        "buffer_before_minutes_snapshot >= 0",
    )
    op.create_check_constraint(
        "buffer_after_snapshot_non_negative",
        "bookings",
        "buffer_after_minutes_snapshot >= 0",
    )
    op.create_check_constraint(
        "reserved_interval_valid",
        "bookings",
        "reserved_ends_at > reserved_starts_at",
    )
    op.create_check_constraint(
        "reserved_contains_service_interval",
        "bookings",
        "reserved_starts_at <= starts_at AND reserved_ends_at >= ends_at",
    )
    op.create_index(
        "ix_bookings_owner_reserved_interval",
        "bookings",
        ["owner_user_id", "reserved_starts_at", "reserved_ends_at"],
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_bookings_prepare_reservation ON bookings")
    op.execute("DROP FUNCTION nails_prepare_booking_reservation()")
    op.drop_index("ix_bookings_owner_reserved_interval", table_name="bookings")
    op.drop_constraint(
        "ck_bookings_reserved_contains_service_interval",
        "bookings",
        type_="check",
    )
    op.drop_constraint(
        "ck_bookings_reserved_interval_valid",
        "bookings",
        type_="check",
    )
    op.drop_constraint(
        "ck_bookings_buffer_after_snapshot_non_negative",
        "bookings",
        type_="check",
    )
    op.drop_constraint(
        "ck_bookings_buffer_before_snapshot_non_negative",
        "bookings",
        type_="check",
    )
    op.drop_constraint(
        "ck_bookings_duration_snapshot_positive",
        "bookings",
        type_="check",
    )
    op.drop_column("bookings", "reserved_ends_at")
    op.drop_column("bookings", "reserved_starts_at")
    op.drop_column("bookings", "buffer_after_minutes_snapshot")
    op.drop_column("bookings", "buffer_before_minutes_snapshot")
    op.drop_column("bookings", "duration_minutes_snapshot")

    op.drop_index(
        "uq_clients_owner_active_normalized_name",
        table_name="clients",
    )
    op.drop_index(
        "uq_services_owner_normalized_public_name",
        table_name="services",
    )
    op.execute("DROP TRIGGER trg_services_normalized_public_name ON services")
    op.execute("DROP FUNCTION nails_normalize_service_public_name()")
    op.drop_column("services", "normalized_public_name")
