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
            "description": "Exact calendar date returned by resolve_date, in YYYY-MM-DD format.",
        },
        "state": {
            "type": "string",
            "enum": ["available", "unavailable", "unknown"],
            "description": (
                "available sets confirmed work intervals; unavailable records a confirmed "
                "day off; unknown removes an accidentally stored date without marking it free."
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
        "Use the current trusted Telegram owner's Nails scheduling data through fixed "
        "operations only. Identity comes from Hermes gateway context and must never be "
        "requested or supplied in arguments. Resolve absolute, month-day, relative, and "
        "weekday-based dates through the backend before using them; never calculate calendar "
        "dates, years, or weekdays in the model. Read services, a concrete calendar day, free "
        "slots, or an exact client match. Replace availability only for explicitly named dates "
        "after a before/after summary and explicit confirmation; unrelated dates are preserved "
        "and existing scheduled bookings are protected. Create a client only after an exact "
        "lookup, a typo check, and explicit user confirmation. Create a booking only after the "
        "client and service are resolved, the chosen time was returned by free_slots, a final "
        "human-readable summary was shown, and the user explicitly confirmed it. Use only "
        "weekday_iso returned by the backend. The runtime generates booking idempotency data "
        "and copies commercial and timing snapshots from backend service data."
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
                    "day_view",
                    "free_slots",
                    "find_client",
                    "create_client",
                    "update_availability",
                    "create_booking",
                ],
                "description": "The single fixed scheduling operation to perform.",
            },
            "date_kind": {
                "type": "string",
                "enum": ["absolute", "month_day", "relative_days", "weekday"],
                "description": "Required only for resolve_date.",
            },
            "day": {
                "type": "string",
                "description": "Concrete calendar date in YYYY-MM-DD format.",
            },
            "month": {
                "type": "integer",
                "minimum": 1,
                "maximum": 12,
                "description": "Calendar month used only for month_day resolution.",
            },
            "day_of_month": {
                "type": "integer",
                "minimum": 1,
                "maximum": 31,
                "description": "Calendar day number used only for month_day resolution.",
            },
            "offset_days": {
                "type": "integer",
                "minimum": -366,
                "maximum": 366,
                "description": "Relative day offset from backend-local today.",
            },
            "weekday_iso": {
                "type": "integer",
                "minimum": 1,
                "maximum": 7,
                "description": "ISO weekday number used only by resolve_date.",
            },
            "occurrence": {
                "type": "string",
                "enum": [
                    "nearest_future",
                    "current_week",
                    "next_week",
                    "current_year",
                    "next_year",
                ],
                "description": "How resolve_date selects a weekday or month-day occurrence.",
            },
            "days": {
                "type": "array",
                "items": _AVAILABILITY_DAY,
                "minItems": 1,
                "maxItems": 31,
                "description": "Only the exact dates to replace through update_availability.",
            },
            "service_name": {
                "type": "string",
                "description": "Public service name, never a technical identifier.",
            },
            "client_public_name": {
                "type": "string",
                "description": "Public client name checked for spelling before creation.",
            },
            "phone": {
                "type": "string",
                "description": "Optional client phone supplied by the user.",
            },
            "start_time": {
                "type": "string",
                "description": "Local start time in HH:MM format from free_slots.",
            },
            "confirmed": {
                "type": "boolean",
                "description": (
                    "Required and true only for create_client, update_availability, or "
                    "create_booking after the user explicitly confirms the immediately "
                    "preceding human-readable summary."
                ),
            },
        },
        "required": ["action"],
    },
}
