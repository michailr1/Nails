NAILS_ONBOARDING = {
    "name": "nails_onboarding",
    "description": (
        "Read or update the current Telegram user's Nails onboarding state. "
        "The user identity is supplied by trusted Hermes gateway context and must never be "
        "requested from the user or included in tool arguments. Use save_schedule_day when the "
        "user gives one day of their weekly schedule. Use confirm_section or complete only after "
        "the user explicitly confirms the shown summary."
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
                    "save_schedule_day",
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
                "enum": ["schedule", "services", "buffers", "bookings"],
                "description": (
                    "Required only for save_section and confirm_section. "
                    "Do not provide it for other actions."
                ),
            },
            "payload": {
                "type": "object",
                "description": (
                    "Required for save_section and save_schedule_day. For save_schedule_day pass "
                    "exactly one day: weekday is Monday=0 through Sunday=6, is_working is boolean, "
                    "and working days also require start_time and end_time in HH:MM format. For a "
                    "non-working day omit both times. For save_section pass the complete section "
                    "draft. Never include credentials or technical identity data."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["action"],
    },
}
