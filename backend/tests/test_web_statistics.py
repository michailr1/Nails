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
    def __init__(self, rows, history_rows=()):
        self._responses = iter((rows, history_rows))
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return _Rows(next(self._responses))


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


def _fixed_item(kind: str, name: str, price: str):
    return {
        "kind": kind,
        "public_name": name,
        "price_type": "fixed",
        "price_amount": price,
        "price_min_amount": None,
    }


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
                    _fixed_item("base", "Маникюр", "2400.00"),
                    _fixed_item("addon", "Снятие", "300.00"),
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
                items=[_fixed_item("base", "Маникюр", "3100.00")],
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
                items=[_fixed_item("base", "Маникюр", "2900.00")],
            ),
            client,
            service,
        ),
    ]
    history_rows = [
        (client_id, "Анна", 3, datetime(2026, 7, 21, 11, 0, tzinfo=UTC))
    ]

    result = web_statistics.get_statistics(
        _Session(rows, history_rows),
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
    assert result.procedures[0].priced_visits_count == 2
    assert result.procedures[0].revenue_amount == Decimal("5500.00")
    assert result.addons[0].name == "Снятие"
    assert result.addons[0].priced_visits_count == 1
    assert result.addons[0].revenue_amount == Decimal("300.00")
    assert result.clients[0].revenue_amount == Decimal("5800.00")
    assert result.clients[0].last_visit_date.isoformat() == "2026-07-21"
    assert result.long_absent_clients == []


def test_statistics_catalog_revenue_uses_snapshot_lower_bound(monkeypatch):
    monkeypatch.setattr(
        web_statistics,
        "get_settings",
        lambda: SimpleNamespace(app_timezone="Europe/Moscow"),
    )
    client = SimpleNamespace(id=uuid.uuid4(), public_name="Анна")
    service = SimpleNamespace(public_name="Педикюр")
    rows = [
        (
            _booking(
                status=BookingStatus.completed,
                starts_at=datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
                ends_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
                price="3500.00",
                source="catalog_range",
                items=[
                    {
                        "kind": "base",
                        "public_name": "Педикюр",
                        "price_type": "range",
                        "price_amount": None,
                        "price_min_amount": "3000.00",
                    },
                    _fixed_item("addon", "Дизайн", "500.00"),
                ],
            ),
            client,
            service,
        )
    ]

    result = web_statistics.get_statistics(
        _Session(rows),
        SimpleNamespace(user_id=uuid.uuid4()),
        date_from=datetime(2026, 7, 20).date(),
        date_to=datetime(2026, 7, 20).date(),
        now=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
    )

    assert result.procedures[0].revenue_amount == Decimal("3000.00")
    assert result.addons[0].revenue_amount == Decimal("500.00")


def test_statistics_does_not_guess_manual_override_distribution(monkeypatch):
    monkeypatch.setattr(
        web_statistics,
        "get_settings",
        lambda: SimpleNamespace(app_timezone="Europe/Moscow"),
    )
    client = SimpleNamespace(id=uuid.uuid4(), public_name="Анна")
    service = SimpleNamespace(public_name="Маникюр")
    rows = [
        (
            _booking(
                status=BookingStatus.completed,
                starts_at=datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
                ends_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
                price="2500.00",
                source="manual_override",
                items=[
                    _fixed_item("base", "Маникюр", "2400.00"),
                    _fixed_item("addon", "Снятие", "300.00"),
                ],
            ),
            client,
            service,
        )
    ]

    result = web_statistics.get_statistics(
        _Session(rows),
        SimpleNamespace(user_id=uuid.uuid4()),
        date_from=datetime(2026, 7, 20).date(),
        date_to=datetime(2026, 7, 20).date(),
        now=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
    )

    assert result.summary.revenue_amount == Decimal("2500.00")
    assert result.procedures[0].visits_count == 1
    assert result.procedures[0].priced_visits_count == 0
    assert result.procedures[0].revenue_amount == Decimal("0.00")
    assert result.addons[0].priced_visits_count == 0
    assert result.addons[0].revenue_amount == Decimal("0.00")


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


def test_long_absent_list_is_rhythm_based_and_self_cleaning(monkeypatch):
    monkeypatch.setattr(
        web_statistics,
        "get_settings",
        lambda: SimpleNamespace(app_timezone="Europe/Moscow"),
    )
    current = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    eligible_id = uuid.uuid4()
    one_visit_id = uuid.uuid4()
    recent_id = uuid.uuid4()
    faded_id = uuid.uuid4()
    boundary_id = uuid.uuid4()
    history_rows = [
        (eligible_id, "Анна", 2, datetime(2026, 5, 20, 9, 0, tzinfo=UTC)),
        (one_visit_id, "Разовая", 1, datetime(2026, 5, 20, 9, 0, tzinfo=UTC)),
        (recent_id, "Недавно", 4, datetime(2026, 6, 20, 9, 0, tzinfo=UTC)),
        (faded_id, "Давно ушла", 8, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)),
        (boundary_id, "На пороге", 3, datetime(2026, 6, 10, 9, 0, tzinfo=UTC)),
    ]
    session = _Session([], history_rows)

    result = web_statistics.get_statistics(
        session,
        SimpleNamespace(user_id=uuid.uuid4()),
        date_from=current.date(),
        date_to=current.date(),
        now=current,
    )

    assert result.long_absent_after_days == 42
    assert result.long_absent_decay_days == 120
    assert [item.client_id for item in result.long_absent_clients] == [eligible_id]
    assert result.long_absent_clients[0].last_visit_date.isoformat() == "2026-05-20"
    assert result.long_absent_clients[0].days_since_last_visit == 63
    assert result.long_absent_clients[0].visits_count == 2

    history_sql = str(session.statements[1])
    assert "clients.profile_status" in history_sql
    assert "clients.owner_user_id" in history_sql
    assert "bookings.owner_user_id" in history_sql
    assert "bookings.status" in history_sql
