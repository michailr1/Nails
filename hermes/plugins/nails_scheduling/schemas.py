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
            "description": "Exact YYYY-MM-DD date returned by resolve_date.",
        },
        "state": {
            "type": "string",
            "enum": ["available", "unavailable", "unknown"],
            "description": (
                "Set work intervals, a day off, or remove an accidentally stored date."
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

_CATALOG_SERVICE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "service_name": {"type": "string"},
        "service_description": {"type": ["string", "null"]},
        "kind": {"type": "string", "enum": ["base", "addon"]},
        "price_type": {
            "type": "string",
            "enum": ["fixed", "range", "per_unit", "on_request"],
        },
        "price_amount": {"type": ["number", "null"], "minimum": 0},
        "price_min_amount": {"type": ["number", "null"], "minimum": 0},
        "price_max_amount": {"type": ["number", "null"], "minimum": 0},
        "price_unit": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
        "sort_order": {"type": "integer", "minimum": 0, "maximum": 1000000},
        "duration_minutes": {
            "type": ["integer", "null"],
            "minimum": 1,
            "maximum": 1440,
            "description": "Suggested duration for a base service.",
        },
        "extra_minutes": {"type": "integer", "minimum": 0, "maximum": 1440},
    },
    "required": [
        "service_name",
        "kind",
        "price_type",
        "duration_minutes",
        "extra_minutes",
    ],
}

NAILS_SCHEDULING = {
    "name": "nails_scheduling",
    "description": (
        "Use only fixed owner-scoped Nails operations. Resolve dates through the backend. "
        "Preview every availability change before confirmation so the master sees the exact "
        "current-to-future intervals and any conflicting bookings. Use list_clients when the "
        "master asks to see all active client cards. Before creating a client, call find_client "
        "and find_client_candidates; when candidates exist, ask the master which existing card "
        "is intended and never create a duplicate without explicit confirmation that this is "
        "another person. When creating a confirmed new client, optional private card fields may "
        "be stored and later read back; private_alias is never a client-facing name. Update or "
        "rename an existing client card only after showing the exact fields to change and "
        "receiving explicit confirmation; omitted fields remain unchanged and null clears a field. "
        "Create a booking from exactly one base service and zero or more addon_names. Preserve "
        "range, per-unit and on-request pricing as estimates unless the master explicitly confirms "
        "price_override_amount. Use duration_override_minutes only when the master explicitly "
        "changes the composed duration. For photo price import, use vision first, show one complete "
        "editable table, label durations as suggestions, and call replace_catalog only after one "
        "explicit confirmation of the whole table. Create, reschedule, cancel, or finalize a "
        "booking only after showing a complete human-readable current-to-future summary and "
        "receiving explicit confirmation. finalize_booking records completed or no_show; omit "
        "price_amount to preserve the booking estimate, or provide it only when the master states "
        "the final total. Rescheduling must use an exact backend free slot. Cancellation is soft "
        "and preserves history. Do not promise an operation before a successful tool result. Send "
        "at most one brief progress message before the final result."
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
                    "replace_catalog",
                    "day_view",
                    "free_slots",
                    "list_clients",
                    "find_client",
                    "find_client_candidates",
                    "create_client",
                    "update_client",
                    "preview_availability",
                    "update_availability",
                    "create_booking",
                    "reschedule_booking",
                    "cancel_booking",
                    "finalize_booking",
                ],
            },
            "date_kind": {
                "type": "string",
                "enum": ["absolute", "month_day", "relative_days", "weekday"],
            },
            "day": {
                "type": "string",
                "description": "Current or target YYYY-MM-DD date.",
            },
            "new_day": {
                "type": "string",
                "description": "New YYYY-MM-DD date for reschedule_booking.",
            },
            "month": {"type": "integer", "minimum": 1, "maximum": 12},
            "day_of_month": {"type": "integer", "minimum": 1, "maximum": 31},
            "offset_days": {"type": "integer", "minimum": -366, "maximum": 366},
            "weekday_iso": {"type": "integer", "minimum": 1, "maximum": 7},
            "occurrence": {
                "type": "string",
                "enum": [
                    "nearest_future",
                    "current_week",
                    "next_week",
                    "current_year",
                    "next_year",
                ],
            },
            "days": {
                "type": "array",
                "items": _AVAILABILITY_DAY,
                "minItems": 1,
                "maxItems": 31,
            },
            "services": {
                "type": "array",
                "items": _CATALOG_SERVICE,
                "minItems": 1,
                "maxItems": 200,
                "description": "Complete desired active catalog for replace_catalog.",
            },
            "include_inactive": {"type": "boolean"},
            "current_service_name": {"type": "string"},
            "service_name": {
                "type": "string",
                "description": "Public base service name for booking actions.",
            },
            "addon_names": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
                "description": "Public addon service names included in the booking.",
            },
            "service_description": {"type": ["string", "null"]},
            "kind": {"type": "string", "enum": ["base", "addon"]},
            "price_type": {
                "type": "string",
                "enum": ["fixed", "range", "per_unit", "on_request"],
            },
            "price_amount": {
                "type": ["number", "null"],
                "minimum": 0,
                "description": (
                    "Catalog amount for service actions, or the explicitly stated final total "
                    "for finalize_booking. Omit for no_show or when preserving the estimate."
                ),
            },
            "price_min_amount": {"type": ["number", "null"], "minimum": 0},
            "price_max_amount": {"type": ["number", "null"], "minimum": 0},
            "price_unit": {"type": ["string", "null"]},
            "price_override_amount": {
                "type": ["number", "null"],
                "minimum": 0,
                "description": "Confirmed final booking price override.",
            },
            "category": {"type": ["string", "null"]},
            "sort_order": {"type": "integer", "minimum": 0, "maximum": 1000000},
            "extra_minutes": {"type": "integer", "minimum": 0, "maximum": 1440},
            "currency": {"type": "string"},
            "duration_minutes": {
                "type": ["integer", "null"],
                "minimum": 1,
                "maximum": 1440,
            },
            "duration_override_minutes": {
                "type": ["integer", "null"],
                "minimum": 1,
                "maximum": 1440,
                "description": "Confirmed final booking duration override.",
            },
            "buffer_before_minutes": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1440,
            },
            "buffer_after_minutes": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1440,
            },
            "is_active": {"type": "boolean"},
            "client_public_name": {
                "type": "string",
                "description": (
                    "Current public client name; check exact and candidate matches before creation."
                ),
            },
            "new_public_name": {
                "type": "string",
                "description": "New public client name for update_client rename.",
            },
            "phone": {"type": ["string", "null"]},
            "private_alias": {
                "type": ["string", "null"],
                "description": "Master-only search alias; never use it to address the client.",
            },
            "contact_channel": {"type": ["string", "null"]},
            "birthday": {
                "type": ["string", "null"],
                "description": "Optional YYYY-MM-DD birthday.",
            },
            "notes": {"type": ["string", "null"]},
            "nail_skin_notes": {"type": ["string", "null"]},
            "sensitivity_notes": {"type": ["string", "null"]},
            "style_preferences": {"type": ["string", "null"]},
            "communication_preferences": {"type": ["string", "null"]},
            "start_time": {
                "type": "string",
                "description": "Current local HH:MM start.",
            },
            "new_start_time": {
                "type": "string",
                "description": "New local HH:MM start for reschedule_booking.",
            },
            "outcome": {
                "type": "string",
                "enum": ["completed", "no_show"],
                "description": "Final visit outcome for finalize_booking.",
            },
            "confirmed": {
                "type": "boolean",
                "description": (
                    "True only after explicit confirmation of the immediately preceding summary."
                ),
            },
        },
        "required": ["action"],
    },
}
