from nails_scheduling.service_catalog import (
    service_catalog_request_spec,
    validate_service_catalog_args,
)


def _update(**overrides):
    payload = {
        "action": "update_service",
        "price_amount": 1700,
        "duration_minutes": 100,
        "buffer_after_minutes": 21,
        "confirmed": True,
    }
    payload.update(overrides)
    return payload


def test_update_service_uses_service_name_as_current_name_when_unchanged():
    action, values = validate_service_catalog_args(
        _update(service_name="Маникюр с покрытием")
    )

    method, path, params, body = service_catalog_request_spec(action, values)

    assert method == "PUT"
    assert path == "/api/v1/scheduling/services"
    assert params is None
    assert body == {
        "public_name": "Маникюр с покрытием",
        "public_description": None,
        "price_amount": "1700.00",
        "currency": "RUB",
        "duration_minutes": 100,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 21,
        "is_active": True,
        "current_public_name": "Маникюр с покрытием",
    }


def test_update_service_uses_current_name_as_future_name_when_not_renamed():
    action, values = validate_service_catalog_args(
        _update(current_service_name="Маникюр с покрытием")
    )

    _, _, _, body = service_catalog_request_spec(action, values)

    assert body["current_public_name"] == "Маникюр с покрытием"
    assert body["public_name"] == "Маникюр с покрытием"
