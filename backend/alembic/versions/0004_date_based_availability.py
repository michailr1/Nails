"""Replace weekly schedule onboarding with date-based availability.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM onboarding_drafts
        WHERE section::text = 'schedule'
        """
    )
    op.execute(
        """
        UPDATE onboarding_states
        SET current_step = 'services'
        WHERE current_step = 'schedule'
        """
    )

    op.execute(
        "ALTER TABLE onboarding_drafts "
        "ALTER COLUMN section TYPE text USING section::text"
    )
    op.execute("DROP TYPE onboarding_section")
    op.execute(
        "CREATE TYPE onboarding_section AS ENUM "
        "('services', 'buffers', 'availability', 'bookings')"
    )
    op.execute(
        "ALTER TABLE onboarding_drafts "
        "ALTER COLUMN section TYPE onboarding_section "
        "USING section::onboarding_section"
    )

    op.drop_table("schedule_rules")

    op.rename_table("schedule_exceptions", "availability_intervals")
    op.alter_column(
        "availability_intervals",
        "is_working",
        new_column_name="is_available",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.alter_column(
        "availability_intervals",
        "reason",
        new_column_name="note",
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )
    op.execute(
        "ALTER TABLE availability_intervals "
        "DROP CONSTRAINT IF EXISTS ck_schedule_exceptions_working_interval_valid"
    )
    op.create_check_constraint(
        "ck_availability_intervals_availability_interval_valid",
        "availability_intervals",
        "(is_available = false AND start_time IS NULL AND end_time IS NULL) OR "
        "(is_available = true AND start_time IS NOT NULL AND end_time IS NOT NULL "
        "AND end_time > start_time)",
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_schedule_exceptions_owner_day "
        "RENAME TO ix_availability_intervals_owner_day"
    )
    op.execute(
        "ALTER TABLE availability_intervals "
        "RENAME CONSTRAINT pk_schedule_exceptions TO pk_availability_intervals"
    )
    op.execute(
        "ALTER TABLE availability_intervals "
        "RENAME CONSTRAINT fk_schedule_exceptions_owner_user_id_users "
        "TO fk_availability_intervals_owner_user_id_users"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE availability_intervals "
        "RENAME CONSTRAINT fk_availability_intervals_owner_user_id_users "
        "TO fk_schedule_exceptions_owner_user_id_users"
    )
    op.execute(
        "ALTER TABLE availability_intervals "
        "RENAME CONSTRAINT pk_availability_intervals TO pk_schedule_exceptions"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_availability_intervals_owner_day "
        "RENAME TO ix_schedule_exceptions_owner_day"
    )
    op.drop_constraint(
        "ck_availability_intervals_availability_interval_valid",
        "availability_intervals",
        type_="check",
    )
    op.alter_column(
        "availability_intervals",
        "note",
        new_column_name="reason",
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "availability_intervals",
        "is_available",
        new_column_name="is_working",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.rename_table("availability_intervals", "schedule_exceptions")
    op.create_check_constraint(
        "ck_schedule_exceptions_working_interval_valid",
        "schedule_exceptions",
        "(is_working = false) OR "
        "(start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)",
    )

    op.create_table(
        "schedule_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("is_working", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="ck_schedule_rules_weekday_range",
        ),
        sa.CheckConstraint(
            "(is_working = false) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)",
            name="ck_schedule_rules_working_interval_valid",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_schedule_rules_valid_date_range",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_schedule_rules_owner_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_rules"),
    )
    op.create_index(
        "ix_schedule_rules_owner_weekday",
        "schedule_rules",
        ["owner_user_id", "weekday"],
    )

    op.execute(
        "ALTER TABLE onboarding_drafts "
        "ALTER COLUMN section TYPE text USING section::text"
    )
    op.execute("DROP TYPE onboarding_section")
    op.execute(
        "CREATE TYPE onboarding_section AS ENUM "
        "('schedule', 'services', 'buffers', 'bookings')"
    )
    op.execute(
        "ALTER TABLE onboarding_drafts "
        "ALTER COLUMN section TYPE onboarding_section "
        "USING section::onboarding_section"
    )
    op.execute(
        "UPDATE onboarding_states SET current_step = 'schedule' "
        "WHERE current_step = 'services'"
    )
