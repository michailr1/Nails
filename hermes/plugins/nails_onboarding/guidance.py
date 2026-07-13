from __future__ import annotations

from typing import Any

_SECTION_ORDER = ("services", "buffers", "availability", "bookings")

_NEXT_PROMPTS = {
    "services": (
        "Continue only the services section. Ask for missing service data or present the "
        "services summary once. Do not discuss buffers until services is confirmed."
    ),
    "buffers": (
        "Services is already confirmed. Do not ask to confirm services again. Continue "
        "only buffers. When all buffer values are known, present the buffers summary "
        "once and accept one clear affirmative reply as confirmation."
    ),
    "availability": (
        "Services and buffers are already confirmed. Do not ask to confirm them again. "
        "Ask only which concrete nearby calendar dates or exact date range the master "
        "plans to work. Never ask for weekdays alone or a repeating weekly schedule."
    ),
    "bookings": (
        "Services, buffers and availability are already confirmed. Do not reconfirm "
        "them. Continue only with existing bookings."
    ),
    None: (
        "All onboarding sections are confirmed. Do not ask for another section "
        "confirmation. Complete onboarding when appropriate."
    ),
}


def build_dialogue_guidance(result: dict[str, Any]) -> dict[str, Any]:
    """Build safe, deterministic dialogue guidance from backend onboarding state."""

    current_step = result.get("current_step")
    if current_step not in {*_SECTION_ORDER, None}:
        current_step = None

    sections = result.get("sections")
    if not isinstance(sections, list):
        sections = []

    confirmed: set[str] = set()
    unconfirmed: set[str] = set()

    for item in sections:
        if not isinstance(item, dict):
            continue
        section = item.get("section")
        if section not in _SECTION_ORDER:
            continue
        if item.get("is_current_revision_confirmed") is True:
            confirmed.add(section)
        else:
            unconfirmed.add(section)

    ordered_confirmed = [section for section in _SECTION_ORDER if section in confirmed]
    ordered_unconfirmed = [section for section in _SECTION_ORDER if section in unconfirmed]

    return {
        "authoritative_current_step": current_step,
        "confirmed_sections": ordered_confirmed,
        "unconfirmed_sections": ordered_unconfirmed,
        "do_not_reconfirm_sections": ordered_confirmed,
        "confirmation_policy": (
            "One explicit confirmation is enough for one current section revision. "
            "A clear reply such as yes, correct or confirm to the immediately preceding "
            "summary counts as confirmation. Never demand a particular confirmation "
            "word and never ask again after is_current_revision_confirmed becomes true."
        ),
        "next_prompt": _NEXT_PROMPTS[current_step],
    }
