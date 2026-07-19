from nails_scheduling.tools import _with_service_create_defaults
from nails_scheduling.validation import _request_spec, _validate_args


def test_minimal_create_service_uses_product_defaults() -> None:
    action, values = _validate_args(
        _with_service_create_defaults(
            {
                "action": "create_service",
                "service_name": "Педикюр",
                "price_amount": 2000,
                "duration_minutes": 90,
                "confirmed": True,
            }
        )
    )

    method, path, params, body = _request_spec(action, values)

    assert method == "POST"
    assert path == "/api/v1/scheduling/services"
    assert params is None
    assert body == {
        "public_name": "Педикюр",
        "public_description": None,
        "price_amount": "2000.00",
        "currency": "RUB",
        "duration_minutes": 90,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "is_active": True,
    }


def test_explicit_service_values_are_still_validated() -> None:
    action, values = _validate_args(
        _with_service_create_defaults(
            {
                "action": "create_service",
                "service_name": "Педикюр",
                "price_amount": 2000,
                "currency": "EUR",
                "duration_minutes": 90,
                "buffer_before_minutes": 10,
                "buffer_after_minutes": 15,
                "is_active": False,
                "confirmed": True,
            }
        )
    )

    assert action == "create_service"
    assert values["currency"] == "EUR"
    assert values["buffer_before_minutes"] == 10
    assert values["buffer_after_minutes"] == 15
    assert values["is_active"] is False
