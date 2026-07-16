from pathlib import Path


def _client_section() -> str:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8").casefold()
    return text.split("## клиентки: точный и похожий поиск", 1)[1].split(
        "## создание записи", 1
    )[0]


def test_new_client_flow_offers_optional_extended_card_fields():
    section = _client_section()

    for phrase in (
        "дополнительные данные сейчас или пропустить",
        "предпочтительный канал связи",
        "день рождения",
        "внутреннее прозвище",
        "особенности ногтей и кожи",
        "чувствительность, реакции и ограничения",
        "предпочтения по форме, длине, цветам и дизайну",
        "предпочтения по общению",
        "все дополнительные поля необязательны",
        "добавить или изменить позже",
        "не задавай вопросы по каждому полю подряд",
        "достаточно публичного имени",
    ):
        assert phrase in section


def test_skill_does_not_claim_client_cards_only_support_name_and_phone():
    section = _client_section()

    assert "только имя и телефон" in section
    assert "не поддерживаются" not in section
    assert "никогда не используй его при обращении к клиентке" in section
