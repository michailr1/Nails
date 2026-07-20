from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_menu_module():
    path = Path(__file__).resolve().parents[2] / "ops" / "telegram" / "configure_bot_menu.py"
    spec = importlib.util.spec_from_file_location("configure_bot_menu", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_portal_command_is_appended_without_losing_existing_commands():
    module = _load_menu_module()

    commands = module.merge_commands(
        [
            {"command": "new", "description": "Start a new session"},
            {"command": "help", "description": "Show help"},
        ]
    )

    assert commands == [
        {"command": "new", "description": "Start a new session"},
        {"command": "help", "description": "Show help"},
        {"command": "portal", "description": "Личный кабинет мастера"},
    ]


def test_portal_command_is_replaced_idempotently_and_invalid_rows_are_ignored():
    module = _load_menu_module()

    commands = module.merge_commands(
        [
            {"command": "/new", "description": "Start a new session"},
            {"command": "portal", "description": "Old portal title"},
            {"command": "portal", "description": "Duplicate"},
            {"command": "", "description": "Broken"},
        ]
    )

    assert commands == [
        {"command": "new", "description": "Start a new session"},
        {"command": "portal", "description": "Личный кабинет мастера"},
    ]
