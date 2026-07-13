NAILS_ONBOARDING = {
    "name": "nails_onboarding",
    "description": (
        "Read or update the current Telegram user's Nails onboarding state and "
        "master communication preferences. The user identity is supplied by trusted "
        "Hermes gateway context and must never be requested from the user or included "
        "in tool arguments. On start, read master preferences before asking schedule "
        "questions. Use save_schedule_day for one weekly schedule day. Use "
        "confirm_section or complete only after explicit user confirmation."
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
                    "Required for save_master_name, save_master_style, save_section "
                    "and save_schedule_day. For save_master_name pass preferred_name. "
                    "For save_master_style pass style as business, friendly, casual, "
                    "playful or custom; details may refine any style and are required "
                    "for custom. For save_schedule_day pass exactly one day: weekday "
                    "is Monday=0 through Sunday=6, is_working is boolean, and working "
                    "days require start_time and end_time in HH:MM format. For "
                    "save_section pass the complete section draft. Never include "
                    "credentials or technical identity data."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["action"],
    },
}
