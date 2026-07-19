import uuid
from decimal import Decimal

from app.models import Booking, Service
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
