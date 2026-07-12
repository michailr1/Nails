from sqlalchemy import inspect

from app.db import get_engine

EXPECTED_TABLES = {
    "users",
    "services",
    "clients",
    "bookings",
    "schedule_rules",
    "schedule_exceptions",
    "audit_events",
    "onboarding_states",
    "onboarding_drafts",
}


def test_migrations_create_expected_tables() -> None:
    inspector = inspect(get_engine())
    assert set(inspector.get_table_names()) >= EXPECTED_TABLES


def test_business_tables_are_scoped_to_an_owner() -> None:
    inspector = inspect(get_engine())
    for table_name in {
        "services",
        "clients",
        "bookings",
        "schedule_rules",
        "schedule_exceptions",
    }:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        assert "owner_user_id" in columns, table_name


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
