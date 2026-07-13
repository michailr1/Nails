"""Regression checks for the human-facing onboarding interview contract."""

from pathlib import Path


def test_onboarding_skill_preserves_dialogue_order_and_presentation() -> None:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-onboarding"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")

    required_phrases = (
        "После сохранения обычных часов запрещено спрашивать",
        "работает ли мастер все дни недели",
        "выбрать вариант «все дни» или «вс–пт»",
        "Не называй обычные часы «базовым графиком»",
        "Есть ли ещё услуги, которые нужно добавить?",
        "не спрашивай на этом шаге про уборку",
        "только после успешного подтверждения `services`",
        "Этот блок обязателен после подтверждения списка услуг",
        "Не объединяй вопрос о перерывах с вопросом о следующей услуге",
        "Нельзя говорить «цена — если хотите»",
        "цену `2 500 ₽`",
        "Если мастер назвала только число",
        "Думаю… (nails_onboarding)",
        "Думаю… (nails_scheduling)",
        "один раз перед всей группой последовательных вызовов",
        "не добавляй эмодзи, шестерёнку",
        "Не добавляй день недели",
        "Никогда не вычисляй и не угадывай день недели по памяти",
        "Успешный `complete` materializes",
        "nails_scheduling action=resolve_date",
        "не предлагай перезапуск настройки для изменения графика",
        "update_availability",
        "повторного прохождения настройки",
    )

    lower_text = text.casefold()
    for phrase in required_phrases:
        assert phrase.casefold() in lower_text


def test_onboarding_skill_routes_post_complete_calendar_changes_to_scheduling() -> None:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-onboarding"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")

    required = (
        "рабочим источником истины является scheduling-календарь",
        "для просмотра дня, поиска окон, изменения конкретных рабочих дат",
        "«убрать ошибочную дату» означает состояние `unknown`",
        "повторный onboarding нужен только если пользователь явно хочет",
    )
    # The first concept is expressed in the scheduling skill; onboarding must still contain
    # the three direct routing rules below.
    assert required[1] in text
    assert required[2] in text
    assert required[3] in text

    forbidden = (
        "для изменения графика нужно заново пройти onboarding",
        "рабочее управление календарём — следующий модуль",
        "изменение рабочих данных и поиск свободных окон станут доступны",
        "не говори «можете менять настройки»",
    )
    for phrase in forbidden:
        assert phrase not in text


def test_onboarding_skill_no_longer_contains_obsolete_materialization_claims() -> None:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-onboarding"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")

    obsolete_phrases = (
        "сам по себе не создаёт рабочие записи",
        "materialization в рабочий календарь выполняется отдельным этапом",
        "Рабочее создание записей и расчёт свободных окон будут materialized",
    )

    for phrase in obsolete_phrases:
        assert phrase not in text
