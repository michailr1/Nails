import json
from pathlib import Path

from nails_scheduling import finalization, tools
from nails_scheduling.schemas import NAILS_SCHEDULING


def _set_context(monkeypatch):
    values = {
        "HERMES_SESSION_PLATFORM": "telegram",
        "HERMES_SESSION_USER_ID": "700000001",
    }
    monkeypatch.setattr(
        tools,
        "_get_session_env",
        lambda name, default="": values.get(name, default),
    )
    monkeypatch.setenv("NAILS_INTERNAL_API_KEY", "k" * 64)


def _booking(
    *,
    status="scheduled",
    price_amount="2500.00",
    price_source="catalog_fixed",
    price_confirmed=True,
):
    starts_at = "2026-07-18T13:00:00+02:00"
    return {
        "id": "22222222-2222-4222-8222-222222222222",
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "addon_names": [],
        "catalog_items": [
            {
                "service_id": "11111111-1111-4111-8111-111111111111",
                "kind": "base",
                "public_name": "Маникюр",
                "price_type": "fixed",
                "price_amount": "2500.00",
                "price_min_amount": None,
                "price_max_amount": None,
                "price_unit": None,
                "currency": "RUB",
                "duration_minutes": 120,
                "extra_minutes": 0,
            }
        ],
        "starts_at": starts_at,
        "ends_at": "2026-07-18T15:00:00+02:00",
        "reserved_starts_at": starts_at,
        "reserved_ends_at": "2026-07-18T15:21:00+02:00",
        "status": status,
        "price_amount": price_amount,
        "currency": "RUB",
        "price_type": "fixed",
        "price_min_amount": "2500.00",
        "price_max_amount": "2500.00",
        "price_unit": None,
        "price_source": price_source,
        "price_confirmed": price_confirmed,
        "duration_minutes": 120,
        "duration_source": "catalog_v2",
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 21,
    }


def _day(bookings):
    return {
        "ok": True,
        "action": "day_view",
        "result": {
            "day": "2026-07-18",
            "timezone": "Europe/Berlin",
            "weekday_iso": 6,
            "availability_known": True,
            "availability": [],
            "bookings": bookings,
        },
    }


def _args(**overrides):
    values = {
        "action": "finalize_booking",
        "client_public_name": "Анна",
        "service_name": "Маникюр",
        "day": "2026-07-18",
        "start_time": "13:00",
        "outcome": "completed",
        "confirmed": True,
    }
    values.update(overrides)
    return values


def test_schema_exposes_finalize_booking():
    properties = NAILS_SCHEDULING["parameters"]["properties"]
    assert "finalize_booking" in properties["action"]["enum"]
    assert properties["outcome"]["enum"] == ["completed", "no_show"]


def test_skill_requires_guarded_finalization_and_unknown_price_safety():
    skill = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    ).read_text(encoding="utf-8").casefold()
    for phrase in (
        "finalize_booking",
        "booking_not_finished",
        "не превращай `on_request`",
        "поздняя фраза",
    ):
        assert phrase in skill


def test_finalize_is_prechecked_written_and_verified(monkeypatch):
    _set_context(monkeypatch)
    calls = []
    original = _booking()
    finalized = _booking(
        status="completed",
        price_amount="2700.00",
        price_source="final_manual_override",
        price_confirmed=True,
    )

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _day([original])
        if len(calls) == 2:
            return {
                "ok": True,
                "action": "finalize_booking",
                "result": {"booking": finalized, "changed": True},
            }
        return _day([finalized])

    monkeypatch.setattr(finalization, "_call_backend", fake_call_backend)

    result = json.loads(tools.nails_scheduling(_args(price_amount=2700)))

    assert result["ok"] is True
    assert result["action"] == "finalize_booking"
    assert result["result"]["changed"] is True
    assert result["result"]["verified"] is True
    assert result["result"]["booking"]["status"] == "completed"
    assert result["result"]["booking"]["price_amount"] == "2700.00"
    assert "id" not in result["result"]["booking"]
    assert all(
        "service_id" not in item
        for item in result["result"]["booking"]["catalog_items"]
    )
    assert [call["path"] for call in calls] == [
        "/api/v1/scheduling/day",
        "/api/v1/scheduling/bookings/finalize",
        "/api/v1/scheduling/day",
    ]
    assert calls[1]["json_body"]["outcome"] == "completed"
    assert calls[1]["json_body"]["price_amount"] == "2700.00"


def test_finalize_verification_mismatch_is_not_success(monkeypatch):
    _set_context(monkeypatch)
    original = _booking()
    finalized = _booking(status="completed")
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _day([original])
        if len(calls) == 2:
            return {
                "ok": True,
                "action": "finalize_booking",
                "result": {"booking": finalized, "changed": True},
            }
        return _day([original])

    monkeypatch.setattr(finalization, "_call_backend", fake_call_backend)

    result = json.loads(tools.nails_scheduling(_args()))

    assert result["ok"] is False
    assert result["error"]["code"] == "mutation_verification_failed"


def test_finalize_requires_confirmation(monkeypatch):
    _set_context(monkeypatch)
    result = json.loads(tools.nails_scheduling(_args(confirmed=False)))
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_no_show_rejects_price(monkeypatch):
    _set_context(monkeypatch)
    result = json.loads(
        tools.nails_scheduling(_args(outcome="no_show", price_amount=100))
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"
