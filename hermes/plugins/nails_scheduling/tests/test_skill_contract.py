from pathlib import Path


def test_skill_preserves_scheduling_confirmation_and_security_contract():
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
        "только по `result.weekday_iso`",
        "Никогда не вычисляй и не угадывай день недели",
        "вызови `action=find_client`",
        "Проверьте, пожалуйста, нет ли опечатки",
        "не вызывай write до явного подтверждения",
        "`confirmed=true`",
        "не является окончательным подтверждением записи",
        "покажи итоговую сводку",
        "Runtime сам генерирует idempotency key",
        "не должен создавать дубль",
        "Не повторяй write бесконечно",
        "Перенос, отмена, изменение записи",
    )
    for phrase in required:
        assert phrase in text
