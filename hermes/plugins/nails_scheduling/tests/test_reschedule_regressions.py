import pytest

from nails_scheduling import operations
from nails_scheduling.presenters import _sanitize_success


def _day_response():
    return {
        "ok": True,
        "action": "day_view",
        "result": {
            "timezone": "Europe/Berlin",
            "bookings": [
                {
                    "client_public_name": "Анна Тестовая",
                    "service_name": "Маникюр",
                    "starts_at": "2026-07-17T11:00:00+02:00",
                }
            ],
        },
    }


def _values():
    return {
        "client_public_name": "Анна Тестовая",
        "service_name": "Маникюр",
        "day": "2026-07-17",
        "start_time": "11:00",
        "new_day": "2026-07-17",
        "new_start_time": "12:00",
    }


def _run(monkeypatch, mutation_response):
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "day_view":
            return _day_response()
        if kwargs["action"] == "free_slots":
            pytest.fail("reschedule must not preflight through free_slots")
        assert kwargs["action"] == "reschedule_booking"
        return mutation_response

    monkeypatch.setattr(operations, "_call_backend", fake_call_backend)
    result = operations._booking_mutation(
        "reschedule_booking",
        _values(),
        telegram_user_id="700000001",
        api_key="k" * 64,
    )
    return result, calls


def test_reschedule_reaches_backend_without_free_slots_precheck(monkeypatch):
    response = {
        "ok": True,
        "action": "reschedule_booking",
        "result": {"changed": True},
    }
    result, calls = _run(monkeypatch, response)

    assert result == response
    assert [call["action"] for call in calls] == [
        "day_view",
        "reschedule_booking",
    ]
    assert calls[-1]["json_body"]["starts_at"] == "2026-07-17T11:00:00+02:00"
    assert (
        calls[-1]["json_body"]["new_starts_at"]
        == "2026-07-17T12:00:00+02:00"
    )


def test_reschedule_preserves_backend_booking_conflict(monkeypatch):
    response = {
        "ok": False,
        "action": "reschedule_booking",
        "error": {"code": "booking_conflict", "message": "conflict"},
    }
    result, _ = _run(monkeypatch, response)
    assert result == response


def test_reschedule_preserves_backend_buffer_conflict(monkeypatch):
    response = {
        "ok": False,
        "action": "reschedule_booking",
        "error": {"code": "buffer_conflict", "message": "conflict"},
    }
    result, _ = _run(monkeypatch, response)
    assert result == response


def test_repeated_reschedule_preserves_changed_false(monkeypatch):
    response = {
        "ok": True,
        "action": "reschedule_booking",
        "result": {"changed": False},
    }
    result, _ = _run(monkeypatch, response)
    assert result == response


@pytest.mark.parametrize(
    "technical_text",
    [
        "one-shot: final answer on stdout, nothing else",
        "Traceback (most recent call last)",
        "tool call result",
        "/opt/nails/repo/secret.txt",
    ],
)
def test_public_presenter_rejects_technical_text(technical_text):
    with pytest.raises(ValueError, match="not public"):
        _sanitize_success(
            "find_client_candidates",
            {"candidates": [{"public_name": technical_text, "phone": None}]},
        )
