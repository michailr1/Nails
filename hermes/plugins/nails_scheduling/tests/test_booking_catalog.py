from nails_scheduling import booking_catalog, presenters, service_catalog
from nails_scheduling.validation import ToolInputError


def test_booking_validator_normalizes_addons_and_overrides():
    values = booking_catalog.validate_catalog_booking_args(
        {
            "action": "create_booking",
            "client_public_name": " Анна ",
            "service_name": " Маникюр ",
            "addon_names": [" Снятие ", "Ремонт"],
            "day": "2026-07-21",
            "start_time": "12:00",
            "price_override_amount": 3100,
            "duration_override_minutes": 150,
            "confirmed": True,
        }
    )

    assert values == {
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "addon_names": ["Снятие", "Ремонт"],
        "day": "2026-07-21",
        "start_time": "12:00",
        "price_override_amount": "3100.00",
        "duration_override_minutes": 150,
    }


def test_addon_catalog_validator_rejects_buffers():
    try:
        service_catalog.validate_service_catalog_args(
            {
                "action": "create_service",
                "service_name": "Снятие",
                "kind": "addon",
                "price_amount": 500,
                "duration_minutes": None,
                "extra_minutes": 20,
                "buffer_before_minutes": 5,
                "buffer_after_minutes": 0,
                "currency": "RUB",
                "is_active": True,
                "confirmed": True,
            }
        )
    except ToolInputError:
        pass
    else:
        raise AssertionError("addon buffers must be rejected")


def test_presenter_preserves_catalog_semantics():
    booking = {
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "addon_names": ["Снятие"],
        "catalog_items": [
            {
                "service_id": "00000000-0000-0000-0000-000000000001",
                "kind": "base",
                "public_name": "Маникюр",
                "price_type": "range",
                "price_amount": None,
                "price_min_amount": "2500.00",
                "price_max_amount": "3000.00",
                "price_unit": None,
                "currency": "RUB",
                "duration_minutes": 120,
                "extra_minutes": 0,
            }
        ],
        "starts_at": "2026-07-21T12:00:00+03:00",
        "ends_at": "2026-07-21T14:20:00+03:00",
        "reserved_starts_at": "2026-07-21T12:00:00+03:00",
        "reserved_ends_at": "2026-07-21T14:20:00+03:00",
        "status": "scheduled",
        "price_amount": None,
        "currency": "RUB",
        "price_type": "range",
        "price_min_amount": "3000.00",
        "price_max_amount": "3500.00",
        "price_unit": None,
        "price_source": "catalog_range",
        "price_confirmed": False,
        "duration_minutes": 140,
        "duration_source": "catalog_v2",
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
    }

    sanitized = presenters._sanitize_success(
        "create_booking",
        {"booking": booking, "created": True},
    )

    assert sanitized["booking"]["addon_names"] == ["Снятие"]
    assert sanitized["booking"]["price_type"] == "range"
    assert sanitized["booking"]["price_amount"] is None
    assert sanitized["booking"]["duration_source"] == "catalog_v2"
