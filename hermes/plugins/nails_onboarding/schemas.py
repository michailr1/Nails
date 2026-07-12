NAILS_ONBOARDING = {
    "name": "nails_onboarding",
    "description": (
        "Read or update the current Telegram user's Nails onboarding state. "
        "The user identity is supplied by trusted Hermes gateway context and must never be "
        "requested from the user or included in tool arguments. Use confirm_section or complete "
        "only after the user explicitly confirms the shown summary."
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
                    "Required only for save_section. The section draft exactly as agreed in the "
                    "current conversation. Never include credentials or technical identity data."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["action"],
    },
}
