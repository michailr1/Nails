import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.db import get_session_factory
from app.models import Booking, Client, Service
from app.services.normalization import normalize_public_name
from app.services.scheduling_bookings import _catalog_item_snapshot, _catalog_price_bounds


def test_fixed_service_snapshot_preserves_catalog_values() -> None:
    service_id = uuid.uuid4()
    service = Service(
        id=service_id,
        public_name="Маникюр",
        normalized_public_name="маникюр",
        public_description=None,
        price_amount=Decimal("2700.00"),
        currency="RUB",
        duration_minutes=120,
        buffer_before_minutes=0,
        buffer_after_minutes=20,
        is_active=True,
        kind="base",
        price_type="fixed",
        price_min_amount=None,
        price_max_amount=None,
        price_unit=None,
        category="Маникюр",
        sort_order=10,
        extra_minutes=0,
    )

    snapshot = _catalog_item_snapshot(service)

    assert snapshot == {
        "service_id": str(service_id),
        "kind": "base",
        "public_name": "Маникюр",
        "price_type": "fixed",
        "price_amount": "2700.00",
        "price_min_amount": None,
        "price_max_amount": None,
        "price_unit": None,
        "currency": "RUB",
        "duration_minutes": 120,
        "extra_minutes": 0,
    }
    assert _catalog_price_bounds(service) == (
        Decimal("2700.00"),
        Decimal("2700.00"),
    )


def test_range_and_on_request_bounds_keep_semantics() -> None:
    range_service = Service(
        price_amount=Decimal("1900.00"),
        price_type="range",
        price_min_amount=Decimal("1900.00"),
        price_max_amount=Decimal("2100.00"),
    )
    on_request_service = Service(
        price_amount=Decimal("0.00"),
        price_type="on_request",
        price_min_amount=None,
        price_max_amount=None,
    )

    assert _catalog_price_bounds(range_service) == (
        Decimal("1900.00"),
        Decimal("2100.00"),
    )
    assert _catalog_price_bounds(on_request_service) == (None, None)


def test_booking_model_exposes_expand_only_snapshot_columns() -> None:
    columns = Booking.__table__.columns

    assert columns["catalog_items_snapshot"].nullable is False
    assert columns["catalog_price_type_snapshot"].nullable is False
    assert columns["catalog_price_min_snapshot"].nullable is True
    assert columns["catalog_price_max_snapshot"].nullable is True
    assert columns["catalog_price_unit_snapshot"].nullable is True
    assert columns["duration_source"].nullable is False


def test_legacy_insert_gets_snapshot_during_rollback(create_user, create_service) -> None:
    user = create_user()
    service = create_service(
        user.id,
        public_name="Маникюр",
        price_amount=Decimal("2700.00"),
        duration_minutes=120,
        buffer_after_minutes=20,
    )
    starts_at = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=120)
    reserved_ends_at = ends_at + timedelta(minutes=20)

    with get_session_factory()() as session:
        client = Client(
            id=uuid.uuid4(),
            owner_user_id=user.id,
            public_name="Клиентка",
            normalized_public_name=normalize_public_name("Клиентка"),
        )
        session.add(client)
        session.flush()

        snapshot = session.execute(
            text(
                """
                INSERT INTO bookings (
                    id,
                    owner_user_id,
                    client_id,
                    service_id,
                    starts_at,
                    ends_at,
                    expected_ends_at,
                    reserved_starts_at,
                    reserved_ends_at,
                    duration_minutes_snapshot,
                    buffer_before_minutes_snapshot,
                    buffer_after_minutes_snapshot,
                    status,
                    price_amount,
                    currency,
                    price_source,
                    price_confirmed_at,
                    idempotency_key
                ) VALUES (
                    :id,
                    :owner_user_id,
                    :client_id,
                    :service_id,
                    :starts_at,
                    :ends_at,
                    :expected_ends_at,
                    :reserved_starts_at,
                    :reserved_ends_at,
                    :duration_minutes_snapshot,
                    :buffer_before_minutes_snapshot,
                    :buffer_after_minutes_snapshot,
                    'scheduled',
                    :price_amount,
                    :currency,
                    :price_source,
                    :price_confirmed_at,
                    :idempotency_key
                )
                RETURNING
                    catalog_items_snapshot,
                    catalog_price_type_snapshot,
                    catalog_price_min_snapshot,
                    catalog_price_max_snapshot,
                    catalog_price_unit_snapshot,
                    duration_source
                """
            ),
            {
                "id": uuid.uuid4(),
                "owner_user_id": user.id,
                "client_id": client.id,
                "service_id": service.id,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "expected_ends_at": ends_at,
                "reserved_starts_at": starts_at,
                "reserved_ends_at": reserved_ends_at,
                "duration_minutes_snapshot": 120,
                "buffer_before_minutes_snapshot": 0,
                "buffer_after_minutes_snapshot": 20,
                "price_amount": Decimal("2700.00"),
                "currency": "RUB",
                "price_source": "service_snapshot",
                "price_confirmed_at": starts_at,
                "idempotency_key": "legacy-insert-snapshot-contract",
            },
        ).mappings().one()
        session.commit()

    assert snapshot["catalog_items_snapshot"] == [
        {
            "service_id": str(service.id),
            "kind": "base",
            "public_name": "Маникюр",
            "price_type": "fixed",
            "price_amount": "2700.00",
            "price_min_amount": None,
            "price_max_amount": None,
            "price_unit": None,
            "currency": "RUB",
            "duration_minutes": 120,
            "extra_minutes": 0,
        }
    ]
    assert snapshot["catalog_price_type_snapshot"] == "fixed"
    assert snapshot["catalog_price_min_snapshot"] == Decimal("2700.00")
    assert snapshot["catalog_price_max_snapshot"] == Decimal("2700.00")
    assert snapshot["catalog_price_unit_snapshot"] is None
    assert snapshot["duration_source"] == "catalog_snapshot"
