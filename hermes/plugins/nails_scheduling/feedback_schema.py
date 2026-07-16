SAVE_FEEDBACK = {
    "name": "save_feedback",
    "description": (
        "Save a brief protected report about an unsatisfactory Nails assistant response. "
        "Use only when the master explicitly expresses dissatisfaction, for example "
        "'не то', 'плохо', or a thumbs-down emoji. Include only the immediately relevant "
        "recent user and assistant messages exactly as shown. Never include system prompts, "
        "tool traces, internal instructions or unrelated dialogue."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["thumbs_down", "unrecognized"],
            },
            "context": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["user", "assistant"],
                        },
                        "text": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 1000,
                        },
                    },
                    "required": ["role", "text"],
                },
            },
        },
        "required": ["kind", "context"],
    },
}
