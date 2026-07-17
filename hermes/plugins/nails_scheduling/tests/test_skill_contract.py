from pathlib import Path


def _skill_text() -> str:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-scheduling"
        / "SKILL.md"
    )
    return skill_path.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_skill_preserves_confirmation_date_and_security_contract():
    text = _skill_text().casefold()
    required = (
        "telegram identity берётся только из trusted gateway context",
        "не передавай технические id",
        "не передавай цену, длительность или buffers",
        "никогда не вычисляет дату, год или день недели самостоятельно",
        "action=resolve_date",
        "date_kind=month_day",
        "occurrence=nearest_future",
        "используй только `result.day` и `result.weekday_iso`",
        "завершённый onboarding **никогда не нужно проходить заново ради изменения",
        "сейчас → будет",
        "update_availability",
        "find_client",
        "не является окончательным подтверждением",
        "idempotency key",
        "не повторяй write бесконечно",
        "перенос, отмена и изменение существующей записи",
        "guarded mutation также `verified=true`",
    )
    for phrase in required:
        assert phrase in text


def test_skill_supports_full_service_management_after_onboarding():
    text = _skill_text().casefold()
    section = _section(text, "## услуги", "## просмотр календаря")
    for marker in (
        "action=list_services",
        "action=find_service",
        "action=create_service",
        "action=update_service",
        "is_active=false",
        "is_active=true",
        "service_name_conflict",
        "snapshots",
    ):
        assert marker in section
    assert "никогда не нужно проходить заново ради изменения услуг" in text
    assert "редактирование услуг пока недоступно" not in text
    assert "для изменения услуг пройдите onboarding заново" not in text


def test_skill_allows_master_preference_changes_after_onboarding():
    text = _skill_text().casefold()
    section = text.split("## настройки мастера", 1)[1]
    for marker in (
        "action=get_master_preferences",
        "action=save_master_name",
        "action=save_master_style",
        "action=save_default_work_hours",
        "не вызывай write",
        "не вызывай save-действие до подтверждения",
        "возвращённое значение совпадает с подтверждённым будущим состоянием",
        "assistant_style",
        "assistant_style_details",
        "сохрани остальные пользовательские детали",
        "не придумывай время окончания",
        "не блокируют явно названную запись",
    ):
        assert marker in section


def test_skill_distinguishes_hint_windows_from_day_off_and_unknown():
    text = _skill_text().casefold()
    section = _section(text, "## просмотр календаря", "## клиентки")
    assert "`unavailable`" in section
    assert "выходной" in section
    assert "`available`" in section
    assert "границы подсказок" in section
    assert "`unknown`" in section
    assert "удаляет сохранённую настройку даты" in section
    assert "10:00–23:00" in section
    assert "не блокируют прямую команду" in section


def test_skill_delegates_reschedule_conflicts_to_backend():
    text = _skill_text().casefold()
    section = _section(text, "## перенос существующей записи", "## отмена записи")
    assert "не вызывай `free_slots`" in section
    assert "вызови `reschedule_booking`" in section
    assert "booking_on_day_off" in section
    assert "booking_overlap" in section
    assert "`ok=true`, `verified=true`" in section
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


def test_skill_makes_fresh_backend_reads_authoritative():
    text = _skill_text().casefold()
    section = _section(
        text,
        "## единственный источник текущего состояния",
        "## составные команды",
    )
    for marker in (
        "свежий результат backend tool",
        "история диалога — только как контекст намерения",
        "вывод модели — никогда не является источником фактического состояния",
        "после каждого write обязательно используй свежий readback",
        "при ошибке read или verification не подменяй данные памятью",
        "внутри одного tool-вызова",
        "`ok=true` и `verified=true`",
    ):
        assert marker in section


def test_compound_commands_preserve_the_dialogue_plan_and_report_each_step():
    text = _skill_text().casefold()
    section = _section(text, "## составные команды", "## безопасность")
    for marker in (
        "внутренний упорядоченный план всех намерений",
        "не теряй оставшиеся шаги после уточнения",
        "он не отменяет остальные намерения исходной команды",
        "отдельная понятная сводка и явное подтверждение",
        "после успешного шага автоматически продолжай следующий незавершённый шаг",
        "ошибка одного шага не стирает остальные",
        "не повторяй неуспешный write автоматически",
        "перечисли каждую исходную часть",
        "не скрывай частичный результат",
        "не обещай атомарность",
        "одним «да» несколько мутаций",
    ):
        assert marker in section


def test_create_booking_uses_guarded_read_write_readback_without_slot_gate():
    text = _skill_text().casefold()
    section = _section(text, "## создание записи", "## перенос существующей записи")
    for marker in (
        "заново найди клиентку",
        "заново найди услугу",
        "не вызывай `free_slots` как предварительный гейт",
        "вызови `create_booking`",
        "guarded action",
        "targeted readback",
        "`ok=true`, `verified=true`",
        "не вызывай отдельный повторный write",
        "booking_on_day_off",
        "booking_overlap",
    ):
        assert marker in section
    assert "после write снова вызови `day_view`" not in section


def test_guarded_mutations_do_not_require_second_model_tool_roundtrip():
    text = _skill_text().casefold()
    source = _section(
        text,
        "## единственный источник текущего состояния",
        "## составные команды",
    )
    reschedule = _section(text, "## перенос существующей записи", "## отмена записи")
    cancel = _section(text, "## отмена записи", "## обратная связь")

    assert "внутри одного tool-вызова" in source
    assert "отдельный последующий `day_view` не вызывай" in source
    assert "`ok=true` и `verified=true`" in source
    assert "для всех остальных write" in source
    assert "guarded action" in reschedule
    assert "ожидаемом новом времени" in reschedule
    assert "guarded action внутри одного вызова" in cancel
    assert "только при `ok=true` и `verified=true`" in cancel
    assert "старое упоминание записи в диалоге" in cancel


def test_skill_file_has_final_newline():
    assert _skill_text().endswith("\n")
