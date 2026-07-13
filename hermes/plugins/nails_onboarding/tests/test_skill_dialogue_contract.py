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
        "не объединяй вопрос о перерывах с вопросом о следующей услуге",
        "Нельзя говорить «цена — если хотите»",
        "цену `2 500 ₽`",
        "если мастер назвала только число",
        "Думаю… (nails_onboarding)",
        "один раз перед всей группой последовательных вызовов",
        "не добавляй эмодзи, шестерёнку",
        "не добавляй день недели",
        "никогда не вычисляй и не угадывай день недели по памяти",
        "успешный `complete` materializes",
        "не говори «можете добавлять записи»",
        "не говори «можете менять настройки»",
        "не обещай поиск свободных окон",
        "Создание новых записей, изменение рабочих данных и поиск свободных окон",
    )

    for phrase in required_phrases:
        assert phrase in text


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
