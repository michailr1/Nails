from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from zoneinfo import ZoneInfo

from app.services import scheduling_digest


def _load_sender() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "ops" / "digest" / "send.py"
    spec = importlib.util.spec_from_file_location("nails_digest_sender_long_absent", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_digest_reuses_statistics_long_absent_selection(monkeypatch):
    history_rows = [("row",)]
    selected = [
        SimpleNamespace(
            client_name="Анна",
            last_visit_date=date(2026, 5, 20),
            days_since_last_visit=63,
            visits_count=3,
        )
    ]
    calls = []

    def fake_history(session, identity, *, current):
        calls.append((session, identity, current))
        return history_rows

    def fake_selection(rows, *, timezone, generated_day):
        assert rows is history_rows
        assert timezone.key == "Europe/Moscow"
        assert generated_day == date(2026, 7, 22)
        return {}, selected

    monkeypatch.setattr(scheduling_digest, "_visit_history_rows", fake_history)
    monkeypatch.setattr(scheduling_digest, "_long_absent_clients", fake_selection)
    monkeypatch.setattr(
        scheduling_digest,
        "app_timezone",
        lambda: ZoneInfo("Europe/Moscow"),
    )

    session = object()
    identity = SimpleNamespace(user_id="owner")
    current = datetime(2026, 7, 22, 20, 0, tzinfo=UTC)
    result = scheduling_digest._digest_long_absent_clients(
        session,
        identity,
        current=current,
        generated_day=date(2026, 7, 22),
    )

    assert calls == [(session, identity, current)]
    assert [item.model_dump(mode="json") for item in result] == [
        {
            "client_name": "Анна",
            "last_visit_date": "2026-05-20",
            "days_since_last_visit": 63,
            "visits_count": 3,
        }
    ]


def test_digest_message_adds_calm_master_only_reminder():
    sender = _load_sender()
    message = sender._message(
        [
            {
                "client_public_name": "Ольга",
                "service_name": "Маникюр",
                "addon_names": [],
                "starts_at": "2026-07-22T11:00:00+03:00",
                "ends_at": "2026-07-22T13:00:00+03:00",
                "price_type": "fixed",
                "price_amount": "2700.00",
                "price_min_amount": "2700.00",
                "price_max_amount": "2700.00",
                "price_unit": None,
                "currency": "RUB",
            }
        ],
        ZoneInfo("Europe/Moscow"),
        date(2026, 7, 22),
        [
            {
                "client_name": "Анна",
                "last_visit_date": "2026-05-20",
                "days_since_last_visit": 63,
                "visits_count": 3,
            }
        ],
    )

    assert "💡 Давно не были" in message
    assert "Анна — последний раз 20.05, 9 нед. назад" in message
    assert "Нэйли никому не пишет сама" in message
    assert "client_id" not in message
    assert "retention" not in message.lower()
