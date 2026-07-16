from pathlib import Path


def _booking_section() -> str:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8").casefold()
    return text.split("## создание записи", 1)[1].split(
        "## перенос существующей записи", 1
    )[0]


def test_new_client_booking_surfaces_card_capabilities_before_creation():
    section = _booking_section()

    for phrase in (
        "если клиентка новая",
        "до создания карточки обязательно скажи мастеру",
        "телефон и канал связи",
        "день рождения",
        "внутреннее прозвище для поиска",
        "особенности ногтей и кожи",
        "чувствительность и ограничения",
        "предпочтения по форме, длине, цветам, дизайну и общению",
        "добавить что-то из этого сейчас или создать карточку только с именем",
        "не задавай вопросы по каждому полю подряд",
        "не блокируй запись из-за пустых дополнительных полей",
        "подсказка обязательна в основном сценарии записи новой клиентки",
        "не повторяй полный список при каждой последующей записи",
    ):
        assert phrase in section
