from pathlib import Path

from nails_scheduling.schemas import NAILS_SCHEDULING
from nails_scheduling.validation import _request_spec, _validate_args


def test_schema_exposes_safe_client_and_booking_management_actions():
    actions = set(
        NAILS_SCHEDULING["parameters"]["properties"]["action"]["enum"]
    )
    assert {"find_client_candidates", "reschedule_booking", "cancel_booking"} <= actions
    assert "new_day" in NAILS_SCHEDULING["parameters"]["properties"]
    assert "new_start_time" in NAILS_SCHEDULING["parameters"]["properties"]


def test_candidate_lookup_uses_fixed_endpoint():
    action, values = _validate_args(
        {"action": "find_client_candidates", "client_public_name": "Аня"}
    )
    assert action == "find_client_candidates"
    assert _request_spec(action, values) == (
        "GET",
        "/api/v1/scheduling/clients/candidates",
        {"public_name": "Аня"},
        None,
    )


def test_booking_mutations_require_confirmation_and_exact_current_state():
    action, values = _validate_args(
        {
            "action": "reschedule_booking",
            "client_public_name": "Анна Тестовая",
            "service_name": "Маникюр",
            "day": "2026-07-17",
            "start_time": "11:00",
            "new_day": "2026-07-17",
            "new_start_time": "14:00",
            "confirmed": True,
        }
    )
    assert action == "reschedule_booking"
    assert values["new_start_time"] == "14:00"

    action, values = _validate_args(
        {
            "action": "cancel_booking",
            "client_public_name": "Анна Тестовая",
            "service_name": "Маникюр",
            "day": "2026-07-17",
            "start_time": "11:00",
            "confirmed": True,
        }
    )
    assert action == "cancel_booking"
    assert values["day"] == "2026-07-17"


def test_skill_requires_candidate_check_soft_cancel_and_single_progress_message():
    skill = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    ).read_text(encoding="utf-8").casefold()
    for phrase in (
        "find_client_candidates",
        "никогда не выбирай похожую карточку автоматически",
        "reschedule_booking",
        "cancel_booking",
        "отмена является мягкой",
        "не отправляй несколько промежуточных сообщений подряд",
    ):
        assert phrase in skill
