from __future__ import annotations

import uuid
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.timezones import (
    owner_timezone,
    owner_timezone_name,
    timezone_from_name,
    validate_timezone_name,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return FakeResult(self.value)


class OwnerMappingSession:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return FakeResult(self.values.get(params["owner_user_id"]))


def test_explicit_timezone_is_validated_and_resolved():
    assert validate_timezone_name("Europe/Moscow") == "Europe/Moscow"
    assert timezone_from_name("Europe/Moscow") == ZoneInfo("Europe/Moscow")


def test_invalid_timezone_is_rejected():
    with pytest.raises(ValueError, match="timezone_unknown"):
        validate_timezone_name("Mars/Olympus")


def test_empty_timezone_is_rejected():
    with pytest.raises(ValueError, match="timezone_required"):
        validate_timezone_name("   ")


def test_owner_timezone_uses_stored_value():
    owner_id = uuid.uuid4()
    session = FakeSession("Asia/Yekaterinburg")

    assert owner_timezone_name(session, owner_id) == "Asia/Yekaterinburg"
    assert owner_timezone(session, owner_id) == ZoneInfo("Asia/Yekaterinburg")
    assert session.calls[0][1] == {"owner_user_id": str(owner_id)}


def test_owner_timezone_null_falls_back_to_previous_global_setting(monkeypatch):
    owner_id = uuid.uuid4()
    session = FakeSession(None)
    monkeypatch.setattr(
        "app.timezones.get_settings",
        lambda: SimpleNamespace(app_timezone="Europe/Moscow"),
    )

    assert owner_timezone_name(session, owner_id) == "Europe/Moscow"
    assert owner_timezone(session, owner_id) == ZoneInfo("Europe/Moscow")


def test_owner_timezone_isolated_by_owner(monkeypatch):
    moscow_owner = uuid.uuid4()
    berlin_owner = uuid.uuid4()
    session = OwnerMappingSession(
        {
            str(moscow_owner): "Europe/Moscow",
            str(berlin_owner): "Europe/Berlin",
        }
    )
    monkeypatch.setattr(
        "app.timezones.get_settings",
        lambda: SimpleNamespace(app_timezone="Asia/Yekaterinburg"),
    )

    assert owner_timezone(session, moscow_owner).key == "Europe/Moscow"
    assert owner_timezone(session, berlin_owner).key == "Europe/Berlin"
    assert [call[1]["owner_user_id"] for call in session.calls] == [
        str(moscow_owner),
        str(berlin_owner),
    ]


def test_fallback_and_explicit_previous_timezone_are_identical(monkeypatch):
    owner_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.timezones.get_settings",
        lambda: SimpleNamespace(app_timezone="Europe/Moscow"),
    )

    fallback = owner_timezone(FakeSession(None), owner_id)
    explicit = owner_timezone(FakeSession("Europe/Moscow"), owner_id)

    assert fallback == explicit
    assert fallback.key == explicit.key == "Europe/Moscow"
