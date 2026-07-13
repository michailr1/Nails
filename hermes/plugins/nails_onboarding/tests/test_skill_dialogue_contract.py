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
    )

    for phrase in required_phrases:
        assert phrase in text
