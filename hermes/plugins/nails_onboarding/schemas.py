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
                    "Required only for save_section. The complete section draft exactly as agreed "
                    "in the current conversation. For one schedule day use save_schedule_day "
                    "instead. Never include credentials or technical identity data."
                ),
                "additionalProperties": True,
            },
            "schedule_day": {
                "type": "object",
                "additionalProperties": False,
                "description": (
                    "Required only for save_schedule_day. One day of the weekly schedule. Monday is "
                    "0 and Sunday is 6. For a working day include start_time and end_time in HH:MM "
                    "format. For a non-working day omit both times."
                ),
                "properties": {
                    "weekday": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 6,
                        "description": "Monday=0, Tuesday=1, ..., Sunday=6.",
                    },
                    "is_working": {
                        "type": "boolean",
                        "description": "True for a working day, false for a day off.",
                    },
                    "start_time": {
                        "type": "string",
                        "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                        "description": "Required for a working day, in HH:MM format.",
                    },
                    "end_time": {
                        "type": "string",
                        "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                        "description": "Required for a working day, in HH:MM format.",
                    },
                },
                "required": ["weekday", "is_working"],
            },
        },
        "required": ["action"],
    },
}
