WEB_LOGIN = {
    "name": "web_login",
    "description": (
        "Read or decide the current master's pending web-login request by the "
        "six-digit number shown in the browser. Reading is safe. The exact Telegram "
        "message 'Нэйли, подтверждаю вход: NNNNNN' is itself a separate explicit "
        "confirmation from the master: call action=approve immediately and do not "
        "ask 'Подтвердить вход?' again. For any other wording, approve or deny only "
        "after a separate explicit conversational confirmation from the master."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "verification_number"],
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "approve", "deny"],
            },
            "verification_number": {
                "type": "string",
                "pattern": "^[0-9]{6}$",
            },
        },
    },
}
