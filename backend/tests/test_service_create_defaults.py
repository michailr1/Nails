from app.schemas.scheduling import ServiceCreateRequest


def test_service_create_request_defaults_optional_technical_fields() -> None:
    request = ServiceCreateRequest.model_validate(
        {
            "public_name": "Педикюр",
            "price_amount": 2000,
            "duration_minutes": 90,
        }
    )

    assert request.currency == "RUB"
    assert request.buffer_before_minutes == 0
    assert request.buffer_after_minutes == 0
    assert request.is_active is True
