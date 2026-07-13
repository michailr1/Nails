from sqlalchemy import inspect

from app.db import get_engine

EXPECTED_TABLES = {
    "users",
    "services",
    "clients",
    "bookings",
    "availability_intervals",
    "audit_events",
    "onboarding_states",
    "onboarding_drafts",
    "master_preferences",
}


def test_migrations_create_expected_tables() -> None:
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())

    assert tables >= EXPECTED_TABLES
    assert "schedule_rules" not in tables
    assert "schedule_exceptions" not in tables


def test_business_tables_are_scoped_to_an_owner() -> None:
    inspector = inspect(get_engine())
    for table_name in {
        "services",
        "clients",
        "bookings",
        "availability_intervals",
    }:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        assert "owner_user_id" in columns, table_name


def test_availability_intervals_are_date_based() -> None:
    inspector = inspect(get_engine())
    columns = {
        column["name"] for column in inspector.get_columns("availability_intervals")
    }

    assert {
        "day",
        "start_time",
        "end_time",
        "is_available",
        "note",
    } <= columns
    assert "weekday" not in columns


def test_telegram_user_id_has_a_unique_constraint() -> None:
    inspector = inspect(get_engine())
    constraints = inspector.get_unique_constraints("users")
    constrained_columns = {
        tuple(constraint["column_names"]) for constraint in constraints
    }
    assert ("telegram_user_id",) in constrained_columns


def test_onboarding_drafts_preserve_confirmed_revision() -> None:
    inspector = inspect(get_engine())
    columns = {
        column["name"] for column in inspector.get_columns("onboarding_drafts")
    }
    assert {
        "payload",
        "confirmed_payload",
        "revision",
        "confirmed_revision",
        "is_confirmed",
    } <= columns
