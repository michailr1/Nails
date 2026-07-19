from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "hermes" / "plugins"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

catalog_batch = importlib.import_module("nails_scheduling.catalog_batch")
validation = importlib.import_module("nails_scheduling.validation")
replace_catalog_request_body = catalog_batch.replace_catalog_request_body
sanitize_replace_catalog_result = catalog_batch.sanitize_replace_catalog_result
validate_replace_catalog_args = catalog_batch.validate_replace_catalog_args
ToolInputError = validation.ToolInputError


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
                "services": [_service("Маникюр"), _service("  маникюр  ")],
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
                "price_amount": "2700.00",
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


def _backend_result(*, verified: bool) -> dict:
    return {
        "changed": True,
        "created_count": 1,
        "updated_count": 0,
        "archived_count": 0,
        "verified": verified,
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


def test_catalog_result_strips_internal_ids_and_preserves_verification() -> None:
    result = sanitize_replace_catalog_result(_backend_result(verified=True))
    assert "id" not in result["services"][0]
    assert result["services"][0]["public_name"] == "Маникюр"
    assert result["verified"] is True


def test_catalog_result_rejects_unverified_success() -> None:
    with pytest.raises(ValueError, match="verified catalog replacement"):
        sanitize_replace_catalog_result(_backend_result(verified=False))
