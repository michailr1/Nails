from __future__ import annotations

import json
import logging
import os
from typing import Any

from .booking_catalog import validate_catalog_booking_args
from .client_cards import (
    create_client_card,
    update_client_card,
    validate_client_card_args,
    validate_client_card_update_args,
)
from .finalization import finalize_booking, validate_finalize_booking_args
from .presenters import _sanitize_success
from .service_catalog import service_catalog_request_spec, validate_service_catalog_args
from .transport import _call_backend, _error
from .validation import ToolInputError, _availability_days, _request_spec, _validate_args
from .verified_operations import _verified_booking_mutation, _verified_create_booking

logger = logging.getLogger(__name__)
_API_KEY_ENV = "NAILS_INTERNAL_API_KEY"
_VERIFIED_ACTIONS = {
    "create_booking",
    "reschedule_booking",
    "cancel_booking",
    "finalize_booking",
}
_SERVICE_CREATE_DEFAULTS = {
    "currency": "RUB",
    "buffer_before_minutes": 0,
    "buffer_after_minutes": 0,
    "is_active": True,
}


class TrustedContextError(RuntimeError):
    pass


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _get_session_env(name: str, default: str = "") -> str:
    from gateway.session_context import get_session_env

    return get_session_env(name, default)


def _trusted_telegram_user_id() -> str:
    platform = _get_session_env("HERMES_SESSION_PLATFORM", "").strip().lower()
    user_id = _get_session_env("HERMES_SESSION_USER_ID", "").strip()
    if platform != "telegram":
        raise TrustedContextError("trusted Telegram context is required")
    if not user_id.isdigit() or int(user_id) <= 0:
        raise TrustedContextError("trusted Telegram user identity is missing")
    return user_id


def _api_key() -> str:
    value = os.getenv(_API_KEY_ENV, "").strip()
    if len(value) < 32:
        raise RuntimeError("Nails scheduling plugin is not configured")
    return value


def _preview_values(args: dict[str, Any]) -> dict[str, Any]:
    if set(args) != {"action", "days"}:
        raise ToolInputError("invalid tool arguments")
    return {"days": _availability_days(args.get("days"))}


def _with_service_create_defaults(args: dict[str, Any]) -> dict[str, Any]:
    if args.get("action") != "create_service":
        return args
    return {**_SERVICE_CREATE_DEFAULTS, **args}


def _sanitize_preview_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict) or not isinstance(result.get("days"), list):
        raise ValueError("invalid availability preview")
    safe_days = []
    for day in result["days"]:
        if not isinstance(day, dict):
            raise ValueError("invalid availability preview day")
        current = day.get("current_availability")
        proposed = day.get("proposed_availability")
        conflicts = day.get("conflicts")
        if not isinstance(current, list) or not isinstance(proposed, list):
            raise ValueError("invalid availability preview intervals")
        if not isinstance(conflicts, list):
            raise ValueError("invalid availability preview conflicts")
        safe_days.append(
            {
                "day": day["day"],
                "weekday_iso": day["weekday_iso"],
                "availability_known": day["availability_known"],
                "current_availability": current,
                "proposed_availability": proposed,
                "changed": day["changed"],
                "can_apply": day["can_apply"],
                "conflicts": conflicts,
            }
        )
    return {"days": safe_days}


def nails_scheduling(args: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        action = args.get("action") if isinstance(args, dict) else None
        if action == "create_client":
            values = validate_client_card_args(args)
        elif action == "update_client":
            values = validate_client_card_update_args(args)
        elif action == "list_clients":
            if set(args) != {"action"}:
                raise ToolInputError("invalid tool arguments")
            values = {}
        elif action == "preview_availability":
            values = _preview_values(args)
        elif action == "create_booking":
            values = validate_catalog_booking_args(args)
        elif action == "finalize_booking":
            values = validate_finalize_booking_args(args)
        elif action in {"create_service", "update_service"}:
            action, values = validate_service_catalog_args(
                _with_service_create_defaults(args)
            )
        else:
            action, values = _validate_args(_with_service_create_defaults(args))
        telegram_user_id = _trusted_telegram_user_id()
        api_key = _api_key()

        if action == "create_client":
            response = create_client_card(
                values,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        elif action == "update_client":
            response = update_client_card(
                values,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        elif action == "list_clients":
            response = _call_backend(
                action=action,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method="GET",
                path="/api/v1/scheduling/clients",
                params=None,
                json_body=None,
            )
        elif action == "preview_availability":
            response = _call_backend(
                action=action,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method="POST",
                path="/api/v1/scheduling/availability/preview",
                params=None,
                json_body={"days": values["days"]},
            )
        elif action == "create_booking":
            response = _verified_create_booking(
                values,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        elif action in {"reschedule_booking", "cancel_booking"}:
            response = _verified_booking_mutation(
                action,
                values,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        elif action == "finalize_booking":
            response = finalize_booking(
                values,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
            )
        else:
            if action in {"create_service", "update_service"}:
                method, path, params, json_body = service_catalog_request_spec(
                    action,
                    values,
                )
            else:
                method, path, params, json_body = _request_spec(action, values)
            response = _call_backend(
                action=action,
                telegram_user_id=telegram_user_id,
                api_key=api_key,
                method=method,
                path=path,
                params=params,
                json_body=json_body,
            )

        if not response.get("ok"):
            return _json_response(response)

        try:
            raw_result = response.get("result")
            if action == "update_client" and not isinstance(raw_result, dict):
                raise ValueError("invalid client update result")
            if action == "preview_availability":
                safe_result = _sanitize_preview_result(raw_result)
            elif action == "finalize_booking":
                safe_result = _sanitize_success("cancel_booking", raw_result)
            else:
                safe_result = (
                    raw_result
                    if action == "update_client"
                    else _sanitize_success(action, raw_result)
                )
            if action in _VERIFIED_ACTIONS:
                if not isinstance(raw_result, dict) or raw_result.get("verified") is not True:
                    raise ValueError("verified mutation result is required")
                safe_result["verified"] = True
        except (KeyError, TypeError, ValueError):
            return _json_response(
                _error(
                    "invalid_backend_response",
                    "Scheduling service returned an invalid response.",
                )
            )

        return _json_response({"ok": True, "action": action, "result": safe_result})
    except ToolInputError:
        return _json_response(
            _error(
                "invalid_arguments",
                "The scheduling tool received invalid arguments.",
            )
        )
    except TrustedContextError:
        return _json_response(
            _error(
                "trusted_context_required",
                "Scheduling is available only from a trusted Telegram session.",
            )
        )
    except RuntimeError:
        logger.error("Nails scheduling plugin configuration is unavailable")
        return _json_response(
            _error(
                "plugin_not_configured",
                "Scheduling integration is not configured.",
            )
        )
    except Exception:
        logger.exception("Unexpected Nails scheduling plugin failure")
        return _json_response(
            _error(
                "internal_tool_error",
                "Scheduling integration failed safely.",
            )
        )
