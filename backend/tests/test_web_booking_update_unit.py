import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models import BookingStatus
from app.services.scheduling_common import SchedulingDomainError
from app.services.web_booking_update import _EDITABLE_STATUSES, _working_price_semantics


def _service(
    *,
    price_type: str,
    amount: str = "0",
    minimum: str | None = None,
    maximum: str | None = None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        currency="RUB",
        price_type=price_type,
        price_amount=Decimal(amount),
        price_min_amount=Decimal(minimum) if minimum is not None else None,
        price_max_amount=Decimal(maximum) if maximum is not None else None,
    )


def test_working_price_sums_fixed_range_and_one_per_unit() -> None:
    semantics = _working_price_semantics(
        [
            _service(price_type="fixed", amount="2700"),
            _service(price_type="range", minimum="300", maximum="700"),
            _service(price_type="per_unit", amount="500"),
        ]
    )

    assert semantics.price_type == "range"
    assert semantics.legacy_amount == Decimal("3500")
    assert semantics.price_min == Decimal("3500")
    assert semantics.price_max == Decimal("3900")
    assert semantics.source == "catalog_estimate"


def test_working_price_does_not_drop_known_subtotal_for_on_request_addon() -> None:
    semantics = _working_price_semantics(
        [
            _service(price_type="fixed", amount="2700"),
            _service(price_type="on_request"),
        ]
    )

    assert semantics.price_type == "range"
    assert semantics.legacy_amount == Decimal("2700")
    assert semantics.source == "catalog_estimate"


def test_working_price_rejects_mixed_currency() -> None:
    rub = _service(price_type="fixed", amount="100")
    eur = _service(price_type="fixed", amount="100")
    eur.currency = "EUR"

    with pytest.raises(SchedulingDomainError, match="catalog_currency_mismatch"):
        _working_price_semantics([rub, eur])


def test_only_scheduled_and_completed_bookings_are_editable() -> None:
    assert {BookingStatus.scheduled, BookingStatus.completed} == _EDITABLE_STATUSES
