from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.scheduling import ServiceCreateRequest


def test_legacy_fixed_service_remains_compatible() -> None:
    request = ServiceCreateRequest.model_validate(
        {
            "public_name": "Маникюр",
            "price_amount": 2700,
            "duration_minutes": 120,
        }
    )

    assert request.kind == "base"
    assert request.price_type == "fixed"
    assert request.price_amount == Decimal("2700")
    assert request.currency == "RUB"
    assert request.sort_order == 0
    assert request.extra_minutes == 0


def test_omitted_price_becomes_on_request() -> None:
    request = ServiceCreateRequest.model_validate(
        {
            "public_name": "Сложный дизайн",
            "duration_minutes": 30,
        }
    )

    assert request.price_type == "on_request"
    assert request.price_amount is None


def test_range_price_requires_ordered_bounds() -> None:
    request = ServiceCreateRequest.model_validate(
        {
            "public_name": "Педикюр",
            "price_type": "range",
            "price_min_amount": 1900,
            "price_max_amount": 2100,
            "duration_minutes": 100,
            "category": " Педикюр ",
            "sort_order": 20,
        }
    )

    assert request.price_amount is None
    assert request.price_min_amount == Decimal("1900")
    assert request.price_max_amount == Decimal("2100")
    assert request.category == "Педикюр"

    with pytest.raises(ValidationError):
        ServiceCreateRequest.model_validate(
            {
                "public_name": "Неверная вилка",
                "price_type": "range",
                "price_min_amount": 2200,
                "price_max_amount": 1800,
                "duration_minutes": 60,
            }
        )


def test_per_unit_addon_uses_extra_minutes() -> None:
    request = ServiceCreateRequest.model_validate(
        {
            "public_name": "Дизайн ногтя",
            "kind": "addon",
            "price_type": "per_unit",
            "price_amount": 100,
            "price_unit": "1 ноготь",
            "extra_minutes": 10,
            "category": "Дизайн",
        }
    )

    assert request.duration_minutes is None
    assert request.extra_minutes == 10
    assert request.price_unit == "1 ноготь"


def test_addon_rejects_base_duration() -> None:
    with pytest.raises(ValidationError):
        ServiceCreateRequest.model_validate(
            {
                "public_name": "Снятие",
                "kind": "addon",
                "price_amount": 100,
                "duration_minutes": 15,
                "extra_minutes": 15,
            }
        )
