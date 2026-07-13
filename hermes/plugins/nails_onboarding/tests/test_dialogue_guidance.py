"""Regression checks for onboarding confirmation and availability prompts."""

from pathlib import Path


def test_registered_schema_uses_authoritative_server_state() -> None:
    plugin_dir = Path(__file__).resolve().parents[1]
    init_text = (plugin_dir / "__init__.py").read_text(encoding="utf-8")

    required_phrases = (
        "from .tools import nails_onboarding",
        "result.current_step",
        "authoritative next section",
        "is_current_revision_confirmed",
        "never ask to confirm that section again",
        "One clear affirmative reply",
        "never demand a particular word",
        "current_step is availability",
        "concrete nearby calendar dates",
        "Never ask for weekdays alone",
        "repeating weekly schedule",
    )

    for phrase in required_phrases:
        assert phrase in init_text


def test_plugin_keeps_original_handler_contract() -> None:
    plugin_dir = Path(__file__).resolve().parents[1]

    assert not (plugin_dir / "handler.py").exists()
    assert not (plugin_dir / "guidance.py").exists()
