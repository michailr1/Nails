from pathlib import Path


def test_skill_preserves_scheduling_confirmation_date_and_security_contract():
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")
    required = (
        "Думаю… (nails_scheduling)",
        "Telegram identity берётся только из trusted gateway context",
        "Не передавай технические идентификаторы",
        "Не передавай цену, валюту, длительность или buffers",
        "никогда не вычисляет дату, год или день недели самостоятельно",
        "action=resolve_date",
        "date_kind=month_day",
        "occurrence=nearest_future",
        "используй только `result.day` и `result.weekday_iso`",
        "завершённый onboarding **никогда не нужно проходить заново",
        "сейчас → будет",
        "action=update_availability",
        "не включай в update даты, которых просьба не касается",
        "существующую активную запись",
        "вызови `action=find_client`",
        "Проверьте, пожалуйста, нет ли опечатки",
        "не вызывай write до явного подтверждения",
        "`confirmed=true`",
        "не является окончательным подтверждением записи",
        "покажи итоговую сводку",
        "Runtime сам генерирует idempotency key",
        "Не повторяй write бесконечно",
        "Перенос, отмена и изменение существующей записи",
    )
    lower_text = text.casefold()
    for phrase in required:
        assert phrase.casefold() in lower_text


def test_skill_distinguishes_unknown_from_unavailable():
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")
    assert "`unknown` — удалить ошибочно сохранённую дату" in text
    assert "`unavailable` — подтверждённый выходной" in text
    assert "«убери 18 июля, я его назвала по ошибке» означает `unknown`" in text
    assert "«18 июля не работаю» означает `unavailable`" in text
