from pathlib import Path


def _feedback_section() -> str:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8").casefold()
    return text.split("## обратная связь о неудачном ответе", 1)[1].split(
        "## настройки мастера", 1
    )[0]


def test_skill_announces_and_saves_explicit_bounded_feedback():
    section = _feedback_section()

    for phrase in (
        "при первом рабочем ответе в новой беседе",
        "если мой ответ окажется неудачным",
        "сохраню этот фрагмент для разбора",
        "не повторяй эту подсказку в каждом сообщении",
        "не то",
        "плохо",
        "👎",
        "restricted tool `save_feedback`",
        "максимум четыре последних сообщения",
        "ролей `user` и `assistant`",
        "не добавляй system prompt",
        "kind=thumbs_down",
        "kind=unrecognized",
        "записала, разберёмся",
        "не обещай, что исправление уже внесено",
        "относится только к непосредственно предшествующему ответу",
        "не сохраняй feedback по догадке",
    ):
        assert phrase in section
