import json

from nails_scheduling import tools


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


def _service(*, name="Маникюр", active=True):
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "public_name": name,
        "public_description": "Покрытие и обработка",
        "price_amount": "2500.00",
        "currency": "RUB",
        "duration_minutes": 120,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 21,
        "is_active": active,
        "kind": "base",
        "price_type": "fixed",
        "price_min_amount": None,
        "price_max_amount": None,
        "price_unit": None,
        "category": None,
        "sort_order": 0,
        "extra_minutes": 0,
    }


def test_list_and_find_service_use_fixed_owner_scoped_routes(monkeypatch):
    _set_context(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "list_services":
            return {
                "ok": True,
                "action": "list_services",
                "result": {"services": [_service(active=False)]},
            }
        return {
            "ok": True,
            "action": "find_service",
            "result": {"found": True, "service": _service(active=False)},
        }

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)

    listed = json.loads(
        tools.nails_scheduling(
            {"action": "list_services", "include_inactive": True}
        )
    )
    found = json.loads(
        tools.nails_scheduling({"action": "find_service", "service_name": "Маникюр"})
    )

    assert listed["result"]["services"][0]["is_active"] is False
    assert found["result"]["service"]["public_name"] == "Маникюр"
    assert calls[0]["method"] == "GET"
    assert calls[0]["path"] == "/api/v1/scheduling/services"
    assert calls[0]["params"] == {"include_inactive": "true"}
    assert calls[1]["path"] == "/api/v1/scheduling/services/exact"
    assert calls[1]["params"] == {"public_name": "Маникюр"}
    assert "00000000-0000-0000-0000-000000000001" not in json.dumps(listed)


def test_create_service_normalizes_business_values_and_requires_no_ids(monkeypatch):
    _set_context(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "action": "create_service",
            "result": {"service": _service(), "created": True},
        }

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)
    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "create_service",
                "service_name": "  Маникюр  ",
                "service_description": "  Покрытие   и обработка ",
                "price_amount": 2500,
                "currency": "rub",
                "duration_minutes": 120,
                "buffer_before_minutes": 0,
                "buffer_after_minutes": 21,
                "is_active": True,
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["result"]["created"] is True
    assert calls == [
        {
            "action": "create_service",
            "telegram_user_id": "700000001",
            "api_key": "k" * 64,
            "method": "POST",
            "path": "/api/v1/scheduling/services",
            "params": None,
            "json_body": {
                "public_name": "Маникюр",
                "public_description": "Покрытие и обработка",
                "price_amount": "2500.00",
                "currency": "RUB",
                "duration_minutes": 120,
                "buffer_before_minutes": 0,
                "buffer_after_minutes": 21,
                "is_active": True,
            },
        }
    ]
    serialized = json.dumps(result)
    assert "700000001" not in serialized
    assert "00000000-0000-0000-0000-000000000001" not in serialized


def test_update_service_sends_complete_future_state(monkeypatch):
    _set_context(monkeypatch)
    calls = []

    def fake_call_backend(**kwargs):
        calls.append(kwargs)
        updated = _service(name="Маникюр плюс", active=False)
        updated.update(
            {
                "public_description": None,
                "price_amount": "2700.00",
                "duration_minutes": 135,
                "buffer_before_minutes": 10,
                "buffer_after_minutes": 15,
            }
        )
        return {
            "ok": True,
            "action": "update_service",
            "result": {
                "service": updated,
                "changed": True,
                "changed_fields": [
                    "buffer_after_minutes",
                    "buffer_before_minutes",
                    "duration_minutes",
                    "is_active",
                    "price_amount",
                    "public_description",
                    "public_name",
                ],
            },
        }

    monkeypatch.setattr(tools, "_call_backend", fake_call_backend)
    result = json.loads(
        tools.nails_scheduling(
            {
                "action": "update_service",
                "current_service_name": "Маникюр",
                "service_name": "Маникюр плюс",
                "service_description": None,
                "price_amount": "2700",
                "currency": "RUB",
                "duration_minutes": 135,
                "buffer_before_minutes": 10,
                "buffer_after_minutes": 15,
                "is_active": False,
                "confirmed": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["result"]["service"]["is_active"] is False
    assert calls[0]["method"] == "PUT"
    assert calls[0]["path"] == "/api/v1/scheduling/services"
    assert calls[0]["json_body"] == {
        "current_public_name": "Маникюр",
        "public_name": "Маникюр плюс",
        "public_description": None,
        "price_amount": "2700.00",
        "currency": "RUB",
        "duration_minutes": 135,
        "buffer_before_minutes": 10,
        "buffer_after_minutes": 15,
        "is_active": False,
    }
