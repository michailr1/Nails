"""Regression checks for deterministic onboarding dialogue progression."""

import runpy
from pathlib import Path


def _build(result: dict) -> dict:
    plugin_dir = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(plugin_dir / "guidance.py"))
    return namespace["build_dialogue_guidance"](result)


def _section(name: str, confirmed: bool) -> dict:
    return {
        "section": name,
        "is_current_revision_confirmed": confirmed,
    }


def test_buffers_step_never_reconfirms_services() -> None:
    guidance = _build(
        {
            "current_step": "buffers",
            "sections": [
                _section("services", True),
                _section("buffers", False),
            ],
        }
    )

    assert guidance["authoritative_current_step"] == "buffers"
    assert guidance["do_not_reconfirm_sections"] == ["services"]
    assert "Do not ask to confirm services again" in guidance["next_prompt"]
    assert "one clear affirmative reply" in guidance["next_prompt"]


def test_availability_step_forbids_weekday_or_recurring_schedule_question() -> None:
    guidance = _build(
        {
            "current_step": "availability",
            "sections": [
                _section("services", True),
                _section("buffers", True),
                _section("availability", False),
            ],
        }
    )

    assert guidance["do_not_reconfirm_sections"] == ["services", "buffers"]
    assert "concrete nearby calendar dates" in guidance["next_prompt"]
    assert "Never ask for weekdays alone" in guidance["next_prompt"]
    assert "repeating weekly schedule" in guidance["next_prompt"]


def test_confirmation_policy_accepts_normal_affirmative_reply_once() -> None:
    guidance = _build(
        {
            "current_step": "buffers",
            "sections": [_section("services", True)],
        }
    )

    policy = guidance["confirmation_policy"]
    assert "One explicit confirmation is enough" in policy
    assert "yes, correct or confirm" in policy
    assert "Never demand a particular confirmation word" in policy
    assert "never ask again" in policy
