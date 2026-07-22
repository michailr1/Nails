WEB_LOGIN = {
    "name": "web_login",
    "description": (
        "Read or decide the current master's pending web-login request by the "
        "six-digit number shown in the browser. Reading is safe. Telegram messages "
        "that explicitly approve the login, including 'Нэйли, подтверждаю вход: "
        "NNNNNN', 'подтверждаю вход NNNNNN', and 'подтверди вход NNNNNN', are "
        "themselves a separate explicit confirmation from the master: call "
        "action=approve immediately and do not ask 'Подтвердить вход?' again. A "
        "bare six-digit number or wording that only asks to inspect the request must "
        "use action=read and requires a separate explicit conversational decision "
        "before approve or deny."
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
