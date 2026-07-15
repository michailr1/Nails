"""Regression checks for onboarding confirmation and completion guidance."""

import ast
from pathlib import Path


def _dialogue_contract(init_text: str) -> str:
    tree = ast.parse(init_text)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id == "_DIALOGUE_CONTRACT":
            value = ast.literal_eval(node.value)
            assert isinstance(value, str)
            return value
    raise AssertionError("_DIALOGUE_CONTRACT assignment not found")


def test_registered_schema_uses_authoritative_server_state() -> None:
    plugin_dir = Path(__file__).resolve().parents[1]
    init_text = (plugin_dir / "__init__.py").read_text(encoding="utf-8")
    contract = _dialogue_contract(init_text)

    assert "from .reliable_tools import nails_onboarding" in init_text
    assert "schema=NAILS_ONBOARDING" in init_text

    required_phrases = (
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
        "preserve the exact ISO calendar date",
        "Do not add or infer a weekday label",
        "unverified weekday must be omitted",
        "successful complete operation materializes",
        "do not promise creating or changing bookings",
        "calculating free slots",
    )

    for phrase in required_phrases:
        assert phrase in contract


def test_plugin_keeps_original_handler_contract() -> None:
    plugin_dir = Path(__file__).resolve().parents[1]

    assert not (plugin_dir / "handler.py").exists()
    assert not (plugin_dir / "guidance.py").exists()
