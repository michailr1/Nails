NAILS_SCHEDULING = {
    "name": "nails_scheduling",
    "description": (
        "Use the current trusted Telegram owner's Nails scheduling data through fixed "
        "operations only. Identity comes from Hermes gateway context and must never be "
        "requested or supplied in arguments. Read services, a concrete calendar day, "
        "free slots, or an exact client match. Create a client only after an exact lookup, "
        "a typo check, and explicit user confirmation. Create a booking only after the "
        "client and service are resolved, the chosen time was returned by free_slots, a "
        "final human-readable summary was shown, and the user explicitly confirmed it. "
        "Use only weekday_iso returned by the backend; never infer a weekday. The runtime "
        "generates booking idempotency data and copies price, currency, duration, and "
        "buffers from backend service data."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_services",
                    "day_view",
                    "free_slots",
                    "find_client",
                    "create_client",
                    "create_booking",
                ],
                "description": "The single fixed scheduling operation to perform.",
            },
            "day": {
                "type": "string",
                "description": "Concrete calendar date in YYYY-MM-DD format.",
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
                    "Required and true only for create_client or create_booking after the "
                    "user explicitly confirms the immediately preceding summary."
                ),
            },
        },
        "required": ["action"],
    },
}
