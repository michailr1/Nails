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
        "Use the current trusted Telegram owner's Nails operational data through fixed "
        "operations only. Identity comes from Hermes gateway context and must never be "
        "requested or supplied in arguments. Onboarding is only initial data entry and must "
        "never be restarted for ordinary changes. Resolve dates through the backend; never "
        "calculate calendar dates, years, or weekdays in the model. Read, create, rename, "
        "change, archive, and reactivate services after an exact lookup, a complete before/after "
        "summary, and explicit confirmation. Service price, duration, and buffer changes affect "
        "future bookings; existing bookings retain their stored commercial and timing snapshots. "
        "Replace availability only for explicitly named dates after confirmation. Create a client "
        "only after exact lookup, typo check, and confirmation. Create a booking only after the "
        "client and service are resolved, the chosen time was returned by free_slots, a final "
        "human-readable summary was shown, and the user explicitly confirmed it. Runtime generates "
        "booking idempotency data and copies snapshots from current backend service data."
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
            "include_inactive": {
                "type": "boolean",
                "description": "For list_services, include archived services when true.",
            },
            "current_service_name": {
                "type": "string",
                "description": "Current exact public name used to locate a service before update.",
            },
            "service_name": {
                "type": "string",
                "description": "Public service name, never a technical identifier.",
            },
            "service_description": {
                "type": ["string", "null"],
                "description": "Optional public service description; null clears it.",
            },
            "price_amount": {
                "type": "number",
                "minimum": 0,
                "description": "Base service price with at most two decimal places.",
            },
            "currency": {
                "type": "string",
                "description": "Three-letter currency code; use RUB when no other currency was named.",
            },
            "duration_minutes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1440,
                "description": "Current service duration for future bookings.",
            },
            "buffer_before_minutes": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1440,
                "description": "Current preparation buffer before future bookings.",
            },
            "buffer_after_minutes": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1440,
                "description": "Current recovery/cleanup buffer after future bookings.",
            },
            "is_active": {
                "type": "boolean",
                "description": (
                    "True makes the service bookable. False archives it without deleting "
                    "existing booking history."
                ),
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
                    "Required and true only for create_service, update_service, create_client, "
                    "update_availability, or create_booking after the user explicitly confirms "
                    "the immediately preceding human-readable summary."
                ),
            },
        },
        "required": ["action"],
    },
}
