from pathlib import Path


def _soul_text() -> str:
    soul_path = (
        Path(__file__).resolve().parents[3]
        / "profiles"
        / "nails"
        / "soul.md"
    )
    return soul_path.read_text(encoding="utf-8")


def test_soul_uses_one_nelly_identity_and_persistent_acquaintance() -> None:
    text = _soul_text().casefold()
    required = (
        "я — нэйли",
        "я не человек и не притворяюсь человеком",
        "action=get_master_preferences",
        "если `preferred_name` отсутствует",
        "по умолчанию обращайся на «вы»",
        "не представляйся повторно после `/new`",
        "не добавляй отдельный флаг знакомства",
        "личность и тёплый тон никогда не заменяют tool-проверки",
    )
    for phrase in required:
        assert phrase in text

    for forbidden in (
        "smart nails",
        "нэйлз",
        "нэли",
        "нэйли или",
    ):
        assert forbidden not in text


def test_soul_file_has_final_newline() -> None:
    assert _soul_text().endswith("\n")
