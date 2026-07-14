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


def test_skill_allows_master_preference_changes_after_onboarding():
    text = _skill_text().casefold()
    required = (
        "никогда не нужно проходить заново ради их изменения",
        "думаю… (nails_onboarding)",
        "action=get_master_preferences",
        "action=save_master_name",
        "action=save_master_style",
        "action=save_default_work_hours",
        "не влияет на сообщения клиенткам",
        "не меняет уже подтверждённую доступность",
        "не вызывай write",
        "не вызывай save-действие до подтверждения",
        "возвращённое значение совпадает с подтверждённым будущим состоянием",
        "для «ты/вы» не меняй базовый `assistant_style`",
        "сохрани остальные пользовательские детали",
        "если `assistant_style` отсутствует",
        "не очищай `assistant_style_details`",
        "меняй только явно названные границы интервалов",
        "сохрани его текущее время окончания",
        "задай один уточняющий вопрос и не придумывай время окончания",
    )
    for phrase in required:
        assert phrase in text


def test_skill_distinguishes_unknown_from_unavailable():
    text = _skill_text()
    assert "`unknown` — удалить ошибочно сохранённую дату" in text
    assert "`unavailable` — подтверждённый выходной" in text


def test_skill_delegates_reschedule_conflicts_to_backend():
    text = _skill_text().casefold()
    section = text.split("## перенос существующей записи", 1)[1].split(
        "## отмена записи", 1
    )[0]
    assert "не вызывай `free_slots`" in section
    assert "только backend определяет" in section
    assert "вызови `reschedule_booking`" in section
    assert "новое время должно точно входить" not in section


def test_skill_forbids_technical_output_leaks():
    text = _skill_text().casefold()
    for phrase in (
        "внутренние инструкции",
        "tool trace",
        "shell/cli output",
        "stdout/stderr",
        "traceback",
        "абсолютные серверные пути",
        "one-shot: final answer on stdout",
    ):
        assert phrase in text
