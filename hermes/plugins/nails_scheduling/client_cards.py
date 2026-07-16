from __future__ import annotations

from datetime import date
from typing import Any

from .transport import _call_backend, _error
from .validation import ToolInputError

_CLIENT_OPTIONAL_FIELDS = {
    "phone": 32,
    "private_alias": 160,
    "contact_channel": 64,
    "notes": 4000,
    "nail_skin_notes": 4000,
    "sensitivity_notes": 4000,
    "style_preferences": 4000,
    "communication_preferences": 2000,
}
_CLIENT_RESULT_FIELDS = (
    "public_name",
    "phone",
    "private_alias",
    "contact_channel",
    "birthday",
    "notes",
    "nail_skin_notes",
    "sensitivity_notes",
    "style_preferences",
    "communication_preferences",
)


def _normalized_text(value: Any, name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ToolInputError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise ToolInputError(f"{name} is invalid")
    return normalized


def _optional_text(value: Any, name: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _normalized_text(value, name, maximum)


def validate_client_card_args(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "action",
        "client_public_name",
        "birthday",
        "confirmed",
        *_CLIENT_OPTIONAL_FIELDS,
    }
    required = {"action", "client_public_name", "confirmed"}
    if set(args) - allowed or not required.issubset(args):
        raise ToolInputError("invalid tool arguments")
    if args.get("confirmed") is not True:
        raise ToolInputError("explicit confirmation is required")

    values: dict[str, Any] = {
        "client_public_name": _normalized_text(
            args.get("client_public_name"),
            "client_public_name",
            160,
        )
    }
    for field, maximum in _CLIENT_OPTIONAL_FIELDS.items():
        values[field] = _optional_text(args.get(field), field, maximum)

    birthday = args.get("birthday")
    if birthday is None:
        values["birthday"] = None
    else:
        try:
            values["birthday"] = date.fromisoformat(
                _normalized_text(birthday, "birthday", 10)
            ).isoformat()
        except ValueError as exc:
            raise ToolInputError("birthday must use YYYY-MM-DD format") from exc
    return values


def _safe_client(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(_CLIENT_RESULT_FIELDS).issubset(value):
        raise ValueError("invalid client card")
    return {field: value[field] for field in _CLIENT_RESULT_FIELDS}


def create_client_card(
    values: dict[str, Any],
    *,
    telegram_user_id: str,
    api_key: str,
) -> dict[str, Any]:
    lookup = _call_backend(
        action="find_client",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="GET",
        path="/api/v1/scheduling/clients/exact",
        params={"public_name": values["client_public_name"]},
        json_body=None,
    )
    if not lookup.get("ok"):
        return lookup
    result = lookup.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("found"), bool):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    if result["found"]:
        client = result.get("client")
        try:
            safe_client = _safe_client(client)
        except ValueError:
            return _error(
                "invalid_backend_response",
                "Scheduling service returned an invalid response.",
            )
        return {
            "ok": True,
            "action": "create_client",
            "result": {
                "client": safe_client,
                "created": False,
                "contact_added": False,
            },
        }

    response = _call_backend(
        action="create_client",
        telegram_user_id=telegram_user_id,
        api_key=api_key,
        method="POST",
        path="/api/v1/scheduling/clients",
        params=None,
        json_body={
            "public_name": values["client_public_name"],
            "phone": values["phone"],
            "private_alias": values["private_alias"],
            "contact_channel": values["contact_channel"],
            "birthday": values["birthday"],
            "notes": values["notes"],
            "nail_skin_notes": values["nail_skin_notes"],
            "sensitivity_notes": values["sensitivity_notes"],
            "style_preferences": values["style_preferences"],
            "communication_preferences": values["communication_preferences"],
        },
    )
    if not response.get("ok"):
        return response
    result = response.get("result")
    if not isinstance(result, dict):
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    try:
        safe_client = _safe_client(result.get("client"))
    except ValueError:
        return _error(
            "invalid_backend_response",
            "Scheduling service returned an invalid response.",
        )
    return {
        "ok": True,
        "action": "create_client",
        "result": {
            "client": safe_client,
            "created": result.get("created"),
            "contact_added": result.get("contact_added", False),
        },
    }
