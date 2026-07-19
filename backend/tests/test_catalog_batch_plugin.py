from __future__ import annotations

import sys
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "hermes" / "plugins"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from nails_scheduling.catalog_batch import (  # noqa: E402
    replace_catalog_request_body,
    sanitize_replace_catalog_result,
    validate_replace_catalog_args,
)
from nails_scheduling.validation import ToolInputError  # noqa: E402


def _service(name: str) -> dict:
    return {
        "service_name": name,
        "service_description": None,
        "kind": "base",
        "price_type": "fixed",
        "price_amount": 2700,
        "price_min_amount": None,
        "price_max_amount": None,
        "price_unit": None,
        "category": "Основное",
        "sort_order": 0,
        "duration_minutes": 120,
        "extra_minutes": 0,
    }


def test_replace_catalog_requires_one_confirmation_for_whole_batch() -> None:
    with pytest.raises(ToolInputError):
        validate_replace_catalog_args(
            {
                "action": "replace_catalog",
                "services": [_service("Маникюр")],
                "confirmed": False,
            }
        )


def test_replace_catalog_rejects_duplicate_public_names() -> None:
    with pytest.raises(ToolInputError):
        validate_replace_catalog_args(
            {
                "action": "replace_catalog",
                "services": [_service("Маникюр"), _service("маникюр")],
                "confirmed": True,
            }
        )


def test_replace_catalog_builds_complete_backend_payload() -> None:
    values = validate_replace_catalog_args(
        {
            "action": "replace_catalog",
            "services": [_service("Маникюр")],
            "confirmed": True,
        }
    )
    body = replace_catalog_request_body(values)
    assert body == {
        "services": [
            {
                "public_name": "Маникюр",
                "public_description": None,
                "price_amount": 2700,
                "currency": "RUB",
                "duration_minutes": 120,
                "buffer_before_minutes": 0,
                "buffer_after_minutes": 0,
                "is_active": True,
                "kind": "base",
                "price_type": "fixed",
                "price_min_amount": None,
                "price_max_amount": None,
                "price_unit": None,
                "category": "Основное",
                "sort_order": 0,
                "extra_minutes": 0,
            }
        ]
    }


def test_catalog_result_strips_internal_ids() -> None:
    result = sanitize_replace_catalog_result(
        {
            "changed": True,
            "created_count": 1,
            "updated_count": 0,
            "archived_count": 0,
            "services": [
                {
                    "id": "internal-id",
                    "public_name": "Маникюр",
                    "public_description": None,
                    "price_amount": "2700.00",
                    "currency": "RUB",
                    "duration_minutes": 120,
                    "buffer_before_minutes": 0,
                    "buffer_after_minutes": 0,
                    "is_active": True,
                    "kind": "base",
                    "price_type": "fixed",
                    "price_min_amount": "2700.00",
                    "price_max_amount": "2700.00",
                    "price_unit": None,
                    "category": "Основное",
                    "sort_order": 0,
                    "extra_minutes": 0,
                }
            ],
        }
    )
    assert "id" not in result["services"][0]
    assert result["services"][0]["public_name"] == "Маникюр"
