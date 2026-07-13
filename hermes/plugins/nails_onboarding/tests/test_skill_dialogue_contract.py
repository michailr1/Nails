"""Regression checks for the human-facing onboarding interview contract."""

from pathlib import Path


def _skill_text() -> str:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-onboarding"
        / "SKILL.md"
    )
    return skill_path.read_text(encoding="utf-8")


def test_onboarding_skill_preserves_dialogue_order_and_presentation() -> None:
    text = _skill_text().casefold()
    required_phrases = (
        "после сохранения обычных часов запрещено спрашивать",
        "работает ли мастер все дни недели",
        "выбрать вариант «все дни» или «вс–пт»",
        "не называй обычные часы «базовым графиком»",
        "есть ли ещё услуги, которые нужно добавить?",
        "не спрашивай на этом шаге про уборку",
        "только после успешного подтверждения `services`",
        "этот блок обязателен после подтверждения списка услуг",
        "не объединяй вопрос о перерывах с вопросом о следующей услуге",
        "нельзя говорить «цена — если хотите»",
        "цену `2 500 ₽`",
        "если мастер назвала только число",
        "думаю… (nails_onboarding)",
        "думаю… (nails_scheduling)",
        "nails_scheduling action=resolve_date",
        "никогда не вычисляет дату, год или день недели самостоятельно",
        "успешный `complete` materializes",
    )
    for phrase in required_phrases:
        assert phrase in text


def test_completed_onboarding_routes_calendar_changes_to_scheduling() -> None:
    text = _skill_text().casefold()
    required_phrases = (
        "не предлагай перезапуск настройки для изменения графика",
        "для просмотра дня, поиска окон, изменения конкретных рабочих дат",
        "`update_availability`",
        "«убрать ошибочную дату» означает состояние `unknown`",
        "повторный onboarding нужен только если пользователь явно хочет",
        "без повторного прохождения настройки",
    )
    for phrase in required_phrases:
        assert phrase in text

    forbidden_phrases = (
        "для изменения графика нужно заново пройти onboarding",
        "рабочее управление календарём — следующий модуль",
        "изменение рабочих данных и поиск свободных окон станут доступны",
        "не говори «можете менять настройки»",
    )
    for phrase in forbidden_phrases:
        assert phrase not in text


def test_onboarding_skill_no_longer_contains_obsolete_materialization_claims() -> None:
    text = _skill_text()
    obsolete_phrases = (
        "сам по себе не создаёт рабочие записи",
        "materialization в рабочий календарь выполняется отдельным этапом",
        "Рабочее создание записей и расчёт свободных окон будут materialized",
    )
    for phrase in obsolete_phrases:
        assert phrase not in text
