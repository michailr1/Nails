_TIME_INTERVAL = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "start_time": {
            "type": "string",
            "description": "Local time in HH:MM format.",
        },
        "end_time": {
            "type": "string",
            "description": "Local time in HH:MM format.",
        },
    },
    "required": ["start_time", "end_time"],
}

_AVAILABILITY_DAY = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "day": {
            "type": "string",
            "description": "Exact YYYY-MM-DD date returned by resolve_date.",
        },
        "state": {
            "type": "string",
            "enum": ["available", "unavailable", "unknown"],
            "description": (
                "Set work intervals, a day off, or remove an accidentally stored date."
            ),
        },
        "intervals": {
            "type": "array",
            "items": _TIME_INTERVAL,
            "maxItems": 4,
        },
        "note": {"type": "string"},
    },
    "required": ["day", "state", "intervals"],
}

NAILS_SCHEDULING = {
    "name": "nails_scheduling",
    "description": (
        "Use only fixed owner-scoped Nails operations. Resolve dates through the backend. "
        "Before creating a client, call find_client and find_client_candidates; when "
        "candidates exist, ask the master which existing card is intended and never "
        "create a duplicate without explicit confirmation that this is another person. "
        "When creating a confirmed new client, optional private card fields may be stored "
        "and later read back; private_alias is never a client-facing name. "
        "Create, reschedule, or cancel a booking only after showing a complete "
        "human-readable current-to-future summary and receiving explicit confirmation. "
        "Rescheduling must use an exact backend free slot. Cancellation is soft and "
        "preserves history. Do not promise an operation before a successful tool result. "
        "Send at most one brief progress message before the final result."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "resolve_date",
                    "list_services",
                    "find_service",
                    "create_service",
                    "update_service",
                    "day_view",
                    "free_slots",
                    "find_client",
                    "find_client_candidates",
                    "create_client",
                    "update_availability",
                    "create_booking",
                    "reschedule_booking",
                    "cancel_booking",
                ],
            },
            "date_kind": {
                "type": "string",
                "enum": ["absolute", "month_day", "relative_days", "weekday"],
            },
            "day": {
                "type": "string",
                "description": "Current or target YYYY-MM-DD date.",
            },
            "new_day": {
                "type": "string",
                "description": "New YYYY-MM-DD date for reschedule_booking.",
            },
            "month": {"type": "integer", "minimum": 1, "maximum": 12},
            "day_of_month": {"type": "integer", "minimum": 1, "maximum": 31},
            "offset_days": {"type": "integer", "minimum": -366, "maximum": 366},
            "weekday_iso": {"type": "integer", "minimum": 1, "maximum": 7},
            "occurrence": {
                "type": "string",
                "enum": [
                    "nearest_future",
                    "current_week",
                    "next_week",
                    "current_year",
                    "next_year",
                ],
            },
            "days": {
                "type": "array",
                "items": _AVAILABILITY_DAY,
                "minItems": 1,
                "maxItems": 31,
            },
            "include_inactive": {"type": "boolean"},
            "current_service_name": {"type": "string"},
            "service_name": {
                "type": "string",
                "description": "Public service name.",
            },
            "service_description": {"type": ["string", "null"]},
            "price_amount": {"type": "number", "minimum": 0},
            "currency": {"type": "string"},
            "duration_minutes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1440,
            },
            "buffer_before_minutes": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1440,
            },
            "buffer_after_minutes": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1440,
            },
            "is_active": {"type": "boolean"},
            "client_public_name": {
                "type": "string",
                "description": (
                    "Public client name; check exact and candidate matches before creation."
                ),
            },
            "phone": {"type": ["string", "null"]},
            "private_alias": {
                "type": ["string", "null"],
                "description": "Master-only search alias; never use it to address the client.",
            },
            "contact_channel": {"type": ["string", "null"]},
            "birthday": {
                "type": ["string", "null"],
                "description": "Optional YYYY-MM-DD birthday.",
            },
            "notes": {"type": ["string", "null"]},
            "nail_skin_notes": {"type": ["string", "null"]},
            "sensitivity_notes": {"type": ["string", "null"]},
            "style_preferences": {"type": ["string", "null"]},
            "communication_preferences": {"type": ["string", "null"]},
            "start_time": {
                "type": "string",
                "description": "Current local HH:MM start.",
            },
            "new_start_time": {
                "type": "string",
                "description": "New local HH:MM start for reschedule_booking.",
            },
            "confirmed": {
                "type": "boolean",
                "description": (
                    "True only after explicit confirmation of the immediately preceding summary."
                ),
            },
        },
        "required": ["action"],
    },
}
