from pathlib import Path


def _skill_text() -> str:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    )
    return skill_path.read_text(encoding="utf-8")


def test_skill_preserves_confirmation_date_and_security_contract():
    text = _skill_text().casefold()
    required = (
        "думаю… (nails_scheduling)",
        "telegram identity берётся только из trusted gateway context",
        "не передавай технические id",
        "не передавай цену, длительность или buffers",
        "никогда не вычисляет дату, год или день недели самостоятельно",
        "action=resolve_date",
        "date_kind=month_day",
        "occurrence=nearest_future",
        "используй только `result.day` и `result.weekday_iso`",
        "завершённый onboarding **никогда не нужно проходить заново ради изменения графика",
        "сейчас → будет",
        "update_availability",
        "активной записи",
        "find_client",
        "не является окончательным подтверждением",
        "idempotency key",
        "не повторяй write бесконечно",
        "перенос, отмена и изменение существующей записи",
    )
    for phrase in required:
        assert phrase in text


def test_skill_supports_full_service_management_after_onboarding():
    text = _skill_text().casefold()
    required = (
        "onboarding — только удобный мастер первоначального заполнения",
        "никогда не нужно проходить заново ради изменения услуг",
        "action=list_services",
        "action=find_service",
        "action=create_service",
        "action=update_service",
        "сейчас → будет",
        "только к будущим записям",
        "сохранят свои согласованные snapshots",
        "удаляются физически",
        "безопасную архивацию",
        "is_active=false",
        "is_active=true",
        "service_name_conflict",
    )
    for phrase in required:
        assert phrase in text

    forbidden = (
        "редактирование услуг пока недоступно",
        "для изменения услуг пройдите onboarding заново",
        "перезапустить настройку",
    )
    for phrase in forbidden:
        assert phrase not in text


def test_skill_distinguishes_unknown_from_unavailable():
    text = _skill_text()
    assert "`unknown` — удалить ошибочно сохранённую дату" in text
    assert "`unavailable` — подтверждённый выходной" in text
