const WORKING_SCHEDULE_DAYS = 14;
const WORKING_SCHEDULE_WEEKDAYS = [
  "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье",
];
const WORKING_SCHEDULE_HELP = "Именно в эти часы клиентки видят свободное время для записи. Конкретные слоты также зависят от длительности процедуры, времени на подготовку и уборку и уже созданных записей.";

function scheduleIsoDate(day) {
  const year = day.getFullYear();
  const month = String(day.getMonth() + 1).padStart(2, "0");
  const date = String(day.getDate()).padStart(2, "0");
  return `${year}-${month}-${date}`;
}

function scheduleDateLabel(value) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" })
    .format(new Date(`${value}T12:00:00`));
}

function scheduleDayText(day) {
  if (!day.availability_known) return "Часы не заданы";
  if (!day.availability.length || day.availability.every((item) => !item.is_available)) {
    return "Выходной";
  }
  return day.availability
    .filter((item) => item.is_available)
    .map((item) => `${String(item.start_time).slice(0, 5)}–${String(item.end_time).slice(0, 5)}`)
    .join(", ");
}

function schedulePayload(day, state, startTime, endTime) {
  if (state === "available") {
    return {
      days: [{
        day,
        state,
        intervals: [{ start_time: startTime, end_time: endTime }],
        note: null,
      }],
    };
  }
  return { days: [{ day, state, intervals: [], note: null }] };
}

function renderWorkingScheduleEditor(panel, day) {
  const existing = day.availability.find((item) => item.is_available) || {};
  const initialState = !day.availability_known
    ? "unknown"
    : existing.start_time
      ? "available"
      : "unavailable";
  const editor = document.createElement("form");
  editor.className = "working-schedule-editor";
  editor.innerHTML = `
    <fieldset>
      <legend>${escapeHtml(WORKING_SCHEDULE_WEEKDAYS[day.weekday_iso - 1])}, ${escapeHtml(scheduleDateLabel(day.day))}</legend>
      <label class="working-schedule-state"><span>Статус дня</span>
        <select name="state">
          <option value="available" ${initialState === "available" ? "selected" : ""}>Рабочий день</option>
          <option value="unavailable" ${initialState === "unavailable" ? "selected" : ""}>Выходной</option>
          <option value="unknown" ${initialState === "unknown" ? "selected" : ""}>Не задано</option>
        </select>
      </label>
      <div class="working-schedule-times">
        <label><span>С</span><input type="time" name="start_time" value="${String(existing.start_time || "10:00").slice(0, 5)}"></label>
        <label><span>До</span><input type="time" name="end_time" value="${String(existing.end_time || "20:00").slice(0, 5)}"></label>
      </div>
      <p class="working-schedule-conflict" role="alert"></p>
      <div class="working-schedule-actions">
        <button class="primary-button" type="submit">Сохранить</button>
        <button class="secondary-button" type="button" data-cancel-schedule>Отмена</button>
      </div>
    </fieldset>`;

  const syncTimes = () => {
    editor.querySelector(".working-schedule-times").hidden = editor.elements.state.value !== "available";
  };
  editor.elements.state.addEventListener("change", syncTimes);
  syncTimes();

  editor.querySelector("[data-cancel-schedule]").addEventListener("click", () => editor.remove());
  editor.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorLine = editor.querySelector(".working-schedule-conflict");
    const submit = editor.querySelector("button[type='submit']");
    errorLine.textContent = "";
    submit.disabled = true;
    const payload = schedulePayload(
      day.day,
      editor.elements.state.value,
      editor.elements.start_time.value,
      editor.elements.end_time.value,
    );
    try {
      const preview = await api("/web/api/schedule/preview", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const previewDay = preview.days[0];
      if (!previewDay.can_apply) {
        const conflicts = previewDay.conflicts
          .map((item) => `${item.client_public_name}, ${String(item.starts_at).slice(11, 16)}–${String(item.ends_at).slice(11, 16)}`)
          .join("; ");
        errorLine.textContent = `Сначала разберитесь с записями: ${conflicts}`;
        submit.disabled = false;
        return;
      }
      await api("/web/api/schedule", { method: "PUT", body: JSON.stringify(payload) });
      await renderWorkingSchedule(panel);
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = "Не удалось сохранить график. Проверьте часы и попробуйте ещё раз.";
      submit.disabled = false;
    }
  });
  panel.querySelector(".working-schedule-editor")?.remove();
  panel.append(editor);
  editor.elements.state.focus();
}

async function renderWorkingSchedule(panel) {
  const today = new Date();
  const until = new Date(today);
  until.setDate(until.getDate() + WORKING_SCHEDULE_DAYS - 1);
  panel.innerHTML = `
    <p class="eyebrow">Доступное время</p>
    <h2>Рабочий график</h2>
    <p class="working-schedule-help">${escapeHtml(WORKING_SCHEDULE_HELP)}</p>
    <p class="muted">Загружаем график…</p>`;
  try {
    const result = await api(`/web/api/schedule?date_from=${scheduleIsoDate(today)}&date_to=${scheduleIsoDate(until)}`);
    panel.innerHTML = `
      <p class="eyebrow">Доступное время</p>
      <h2>Рабочий график</h2>
      <p class="working-schedule-help">${escapeHtml(WORKING_SCHEDULE_HELP)}</p>
      <p class="working-schedule-timezone">Часовой пояс: ${escapeHtml(result.timezone)}</p>
      <div class="working-schedule-days"></div>`;
    const list = panel.querySelector(".working-schedule-days");
    result.days.forEach((day) => {
      const card = document.createElement("article");
      card.className = "working-schedule-day";
      card.innerHTML = `
        <div>
          <strong>${escapeHtml(WORKING_SCHEDULE_WEEKDAYS[day.weekday_iso - 1])}</strong>
          <span>${escapeHtml(scheduleDateLabel(day.day))}</span>
        </div>
        <div class="working-schedule-value">
          <span>${escapeHtml(scheduleDayText(day))}</span>
          ${day.booking_count ? `<small>${day.booking_count} ${day.booking_count === 1 ? "запись" : "записи"}</small>` : ""}
        </div>
        <button class="secondary-button" type="button">Изменить</button>`;
      card.querySelector("button").addEventListener("click", () => renderWorkingScheduleEditor(panel, day));
      list.append(card);
    });
  } catch (error) {
    panel.innerHTML = `
      <p class="eyebrow">Доступное время</p>
      <h2>Рабочий график</h2>
      <p class="booking-edit-error">Не удалось загрузить график.</p>`;
  }
}

const renderPublicProfileBeforeSchedule = renderPublicProfileSetup;
renderPublicProfileSetup = function renderPublicProfileWithSchedule(reachability) {
  renderPublicProfileBeforeSchedule(reachability);
  const page = document.querySelector("#page-content");
  if (!page || page.querySelector(".working-schedule-panel")) return;
  const panel = document.createElement("section");
  panel.className = "panel working-schedule-panel";
  const profilePanel = page.querySelector(".client-public-profile-panel");
  if (profilePanel) profilePanel.after(panel);
  else page.prepend(panel);
  renderWorkingSchedule(panel);
};
