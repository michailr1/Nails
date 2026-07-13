"""Regression checks for structured onboarding section payloads."""

import runpy
from pathlib import Path


def _schema() -> dict:
    plugin_dir = Path(__file__).resolve().parents[1]
    return runpy.run_path(str(plugin_dir / "schemas.py"))["NAILS_ONBOARDING"]


def test_buffer_payload_uses_only_supported_backend_fields() -> None:
    schema = _schema()
    payload = schema["parameters"]["properties"]["payload"]
    buffer_item = payload["properties"]["buffers"]["items"]

    assert payload["additionalProperties"] is False
    assert buffer_item["additionalProperties"] is False
    assert set(buffer_item["properties"]) == {
        "service_name",
        "before_minutes",
        "after_minutes",
    }
    assert set(buffer_item["required"]) == {
        "service_name",
        "before_minutes",
        "after_minutes",
    }


def test_buffer_schema_explains_direction_and_rejects_invented_aliases() -> None:
    schema = _schema()
    description = schema["description"]
    payload_description = schema["parameters"]["properties"]["payload"]["description"]

    assert "before_minutes" in description
    assert "after_minutes" in description
    assert "buffer_minutes" in description
    assert "cleanup_minutes" in description
    assert "single duration" in payload_description
    assert "ambiguous" in payload_description
