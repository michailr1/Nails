from pathlib import Path


SKILL_PATH = (
    Path(__file__).resolve().parents[3]
    / "skills"
    / "nails-onboarding"
    / "SKILL.md"
)


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_default_hours_do_not_turn_into_weekly_schedule_questions() -> None:
    text = _skill_text()

    assert "После сохранения обычных часов запрещено спрашивать" in text
    assert "работает ли мастер все дни недели" in text
    assert "выбрать вариант «все дни» или «вс–пт»" in text
    assert "Не называй обычные часы «базовым графиком»" in text


def test_services_are_completed_before_buffers_are_collected() -> None:
    text = _skill_text()

    assert "Есть ли ещё услуги, которые нужно добавить?" in text
    assert "не спрашивай на этом шаге про уборку" in text
    assert "только после успешного подтверждения `services`" in text
    assert "Этот блок обязателен после подтверждения списка услуг" in text
    assert "не объединяй вопрос о перерывах с вопросом о следующей услуге" in text


def test_price_is_required_and_rub_is_the_default() -> None:
    text = _skill_text()

    assert "Нельзя говорить «цена — если хотите»" in text
    assert "цена `2 500 ₽`" in text
    assert "если мастер назвала только число" in text


def test_custom_tool_thinking_message_is_defined() -> None:
    text = _skill_text()

    assert "Думаю… (nails_onboarding)" in text
    assert "один раз перед всей группой последовательных вызовов" in text
    assert "не добавляй эмодзи, шестерёнку" in text
