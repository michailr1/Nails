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

_SERVICE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "public_name": {"type": "string"},
        "public_description": {"type": "string"},
        "price_amount": {
            "anyOf": [{"type": "number"}, {"type": "string"}],
            "description": "Base service price. A price without a currency is RUB.",
        },
        "currency": {
            "type": "string",
            "description": "Three-letter uppercase currency code. Defaults to RUB.",
        },
        "duration_minutes": {"type": "integer", "minimum": 5, "maximum": 1440},
    },
    "required": ["public_name", "price_amount", "duration_minutes"],
}

_BUFFER = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "service_name": {
            "type": "string",
            "description": "Exact public name of a previously confirmed service.",
        },
        "before_minutes": {
            "type": "integer",
            "minimum": 0,
            "maximum": 240,
            "description": "Reserved minutes before the service. Use 0 when none.",
        },
        "after_minutes": {
            "type": "integer",
            "minimum": 0,
            "maximum": 240,
            "description": "Reserved minutes after the service. Use 0 when none.",
        },
    },
    "required": ["service_name", "before_minutes", "after_minutes"],
}

_AVAILABILITY_DAY = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "day": {"type": "string", "description": "Calendar date in YYYY-MM-DD format."},
        "is_available": {"type": "boolean"},
        "intervals": {"type": "array", "items": _TIME_INTERVAL},
        "note": {"type": "string"},
    },
    "required": ["day", "is_available", "intervals"],
}

_BOOKING = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "client_public_name": {"type": "string"},
        "client_phone": {"type": "string"},
        "service_name": {"type": "string"},
        "starts_at": {
            "type": "string",
            "description": "ISO 8601 date and time including timezone offset.",
        },
    },
    "required": ["client_public_name", "service_name", "starts_at"],
}


NAILS_ONBOARDING = {
    "name": "nails_onboarding",
    "description": (
        "Read or update the current Telegram user's Nails onboarding state and "
        "master preferences. The user identity is supplied by trusted Hermes gateway "
        "context and must never be requested from the user or included in tool "
        "arguments. Before the business interview, collect the preferred name, "
        "assistant style and reusable default work hours. Default work hours are only "
        "a suggested time range and never create availability without confirmation of "
        "concrete dates. Collect services, buffers, availability on concrete dates and "
        "existing bookings. Use confirm_section or complete only after explicit user "
        "confirmation. A buffers draft must be shaped exactly as "
        "{'buffers': [{'service_name': 'Маникюр', 'before_minutes': 0, "
        "'after_minutes': 23}]}; never invent buffer_minutes, cleanup_minutes or "
        "other buffer field names."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "start",
                    "get_state",
                    "get_master_preferences",
                    "save_master_name",
                    "save_master_style",
                    "save_default_work_hours",
                    "save_section",
                    "confirm_section",
                    "pause",
                    "resume",
                    "complete",
                ],
                "description": "The single onboarding operation to perform.",
            },
            "section": {
                "type": "string",
                "enum": ["services", "buffers", "availability", "bookings"],
                "description": (
                    "Required only for save_section and confirm_section. "
                    "Do not provide it for other actions."
                ),
            },
            "payload": {
                "type": "object",
                "description": (
                    "Required for save_master_name, save_master_style, "
                    "save_default_work_hours and save_section. For buffers, the only "
                    "valid top-level key is buffers and every item must use exactly "
                    "service_name, before_minutes and after_minutes. A single duration "
                    "without a before/after direction is ambiguous and must be clarified "
                    "with the user before calling the tool. Availability always uses "
                    "concrete calendar dates, never weekdays or a repeating weekly "
                    "schedule. Never include credentials or technical identity data."
                ),
                "additionalProperties": False,
                "properties": {
                    "preferred_name": {"type": "string"},
                    "style": {
                        "type": "string",
                        "enum": ["business", "friendly", "casual", "playful", "custom"],
                    },
                    "details": {"type": "string"},
                    "intervals": {"type": "array", "items": _TIME_INTERVAL, "maxItems": 4},
                    "services": {"type": "array", "items": _SERVICE, "minItems": 1},
                    "buffers": {"type": "array", "items": _BUFFER},
                    "days": {"type": "array", "items": _AVAILABILITY_DAY, "minItems": 1},
                    "bookings": {"type": "array", "items": _BOOKING},
                },
            },
        },
        "required": ["action"],
    },
}
