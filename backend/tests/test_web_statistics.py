from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import app.services.web_statistics as web_statistics
from app.models import BookingStatus


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _statement):
        return _Rows(self._rows)


def _booking(
    *,
    status: BookingStatus,
    starts_at: datetime,
    ends_at: datetime,
    price: str,
    source: str = "catalog_fixed",
    items=None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        starts_at=starts_at,
        ends_at=ends_at,
        price_amount=Decimal(price),
        price_source=source,
        catalog_items_snapshot=items or [],
    )


def test_statistics_counts_ended_scheduled_visit_without_manual_confirmation(
    monkeypatch,
):
    monkeypatch.setattr(
        web_statistics,
        "get_settings",
        lambda: SimpleNamespace(app_timezone="Europe/Moscow"),
    )
    owner_id = uuid.uuid4()
    client_id = uuid.uuid4()
    client = SimpleNamespace(id=client_id, public_name="Анна")
    service = SimpleNamespace(public_name="Маникюр")
    rows = [
        (
            _booking(
                status=BookingStatus.scheduled,
                starts_at=datetime(2026, 7, 21, 8, 0, tzinfo=UTC),
                ends_at=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
                price="2700.00",
                items=[
                    {"kind": "base", "public_name": "Маникюр"},
                    {"kind": "addon", "public_name": "Снятие"},
                ],
            ),
            client,
            service,
        ),
        (
            _booking(
                status=BookingStatus.completed,
                starts_at=datetime(2026, 7, 21, 11, 0, tzinfo=UTC),
                ends_at=datetime(2026, 7, 21, 13, 0, tzinfo=UTC),
                price="3100.00",
            ),
            client,
            service,
        ),
        (
            _booking(
                status=BookingStatus.scheduled,
                starts_at=datetime(2026, 7, 21, 16, 0, tzinfo=UTC),
                ends_at=datetime(2026, 7, 21, 18, 0, tzinfo=UTC),
                price="2900.00",
            ),
            client,
            service,
        ),
    ]

    result = web_statistics.get_statistics(
        _Session(rows),
        SimpleNamespace(user_id=owner_id),
        date_from=datetime(2026, 7, 21).date(),
        date_to=datetime(2026, 7, 21).date(),
        now=datetime(2026, 7, 21, 15, 0, tzinfo=UTC),
    )

    assert result.summary.revenue_amount == Decimal("5800.00")
    assert result.summary.confirmed_revenue_amount == Decimal("3100.00")
    assert result.summary.estimated_revenue_amount == Decimal("2700.00")
    assert result.summary.visits_count == 2
    assert result.summary.confirmed_visits_count == 1
    assert result.summary.assumed_visits_count == 1
    assert result.summary.average_check_amount == Decimal("2900.00")
    assert result.procedures[0].name == "Маникюр"
    assert result.procedures[0].visits_count == 2
    assert result.addons[0].name == "Снятие"
    assert result.clients[0].revenue_amount == Decimal("5800.00")


def test_statistics_excludes_cancelled_and_no_show_and_keeps_unknown_price_visible(
    monkeypatch,
):
    monkeypatch.setattr(
        web_statistics,
        "get_settings",
        lambda: SimpleNamespace(app_timezone="Europe/Moscow"),
    )
    client = SimpleNamespace(id=uuid.uuid4(), public_name="Оксана")
    service = SimpleNamespace(public_name="Педикюр")
    starts_at = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    ends_at = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    rows = [
        (
            _booking(
                status=BookingStatus.cancelled,
                starts_at=starts_at,
                ends_at=ends_at,
                price="2800.00",
            ),
            client,
            service,
        ),
        (
            _booking(
                status=BookingStatus.no_show,
                starts_at=starts_at,
                ends_at=ends_at,
                price="2800.00",
            ),
            client,
            service,
        ),
        (
            _booking(
                status=BookingStatus.scheduled,
                starts_at=starts_at,
                ends_at=ends_at,
                price="0.00",
                source="final_price_unknown",
            ),
            client,
            service,
        ),
    ]

    result = web_statistics.get_statistics(
        _Session(rows),
        SimpleNamespace(user_id=uuid.uuid4()),
        date_from=datetime(2026, 7, 20).date(),
        date_to=datetime(2026, 7, 20).date(),
        now=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
    )

    assert result.summary.revenue_amount == Decimal("0.00")
    assert result.summary.visits_count == 1
    assert result.summary.cancelled_count == 1
    assert result.summary.no_show_count == 1
    assert result.summary.unknown_price_count == 1
    assert result.summary.average_check_amount is None
