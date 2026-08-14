let calendarAvailabilityDays = new Map();

function calendarAvailabilityTime(value) {
  return String(value || "").slice(0, 5);
}

function calendarScheduleDay(iso) {
  return calendarAvailabilityDays.get(iso) || null;
}

function calendarDayStatus(iso) {
  const day = calendarScheduleDay(iso);
  if (!day || !day.availability_known) {
    return { off: false, label: "По обычному графику", detail: "" };
  }
  const unavailable = (day.availability || []).find((item) => item.is_available === false);
  if (unavailable) {
    return { off: true, label: "Выходной", detail: unavailable.note || "Не работаю" };
  }
  const intervals = (day.availability || []).filter((item) => item.is_available);
  if (!intervals.length) {
    return { off: false, label: "По обычному графику", detail: "" };
  }
  return {
    off: false,
    label: intervals.map((item) => `${calendarAvailabilityTime(item.start_time)}–${calendarAvailabilityTime(item.end_time)}`).join(", "),
    detail: "Другое время",
  };
}

const apiBeforeCalendarAvailability = api;
api = async function apiWithCalendarAvailability(path, options = {}) {
  const payload = await apiBeforeCalendarAvailability(path, options);
  if (String(path).startsWith("/web/api/calendar?")) {
    const params = new URL(path, window.location.origin).searchParams;
    const from = params.get("date_from");
    const to = params.get("date_to");
    if (from && to) {
      const schedule = await apiBeforeCalendarAvailability(
        `/web/api/schedule?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`,
      );
      calendarAvailabilityDays = new Map((schedule.days || []).map((day) => [day.day, day]));
    } else {
      calendarAvailabilityDays = new Map();
    }
  }
  return payload;
};

function calendarAvailabilityBadge(iso) {
  const status = calendarDayStatus(iso);
  if (status.off) return '<span class="calendar-day-off">Выходной</span>';
  if (status.detail) return `<span class="calendar-day-hours">${escapeHtml(status.label)}</span>`;
  return "";
}

function calendarDayExceptionControls(iso) {
  const status = calendarDayStatus(iso);
  return `<section class="calendar-day-exception" aria-label="Рабочее время на этот день">
    <div class="calendar-day-exception-copy">
      <strong>${status.off ? "Выходной" : "Рабочее время"}</strong>
      <span class="muted small">${escapeHtml(status.label)}</span>
    </div>
    <div class="calendar-day-exception-actions">
      <button class="secondary-button" type="button" data-day-off="${iso}">Не работаю в этот день</button>
      <button class="secondary-button" type="button" data-day-hours="${iso}">Другое время в этот день</button>
    </div>
  </section>`;
}

dayPanel = function dayPanelWithAvailability(data, iso) {
  const bookings = bookingsForDate(data, iso);
  const title = dateLabel(iso, { weekday: "long", day: "numeric", month: "long" });
  return `<div class="panel"><div class="panel-header calendar-day-heading"><div><h2>${escapeHtml(title)}</h2>${calendarAvailabilityBadge(iso)}</div><span class="muted small">${bookings.length} записей</span></div>
    ${calendarDayExceptionControls(iso)}
    ${bookings.length ? `<div class="list">${bookings.map((item) => bookingCard(item, data.timezone)).join("")}</div>` : `<div class="empty">На этот день записей нет.</div>`}
  </div>`;
};

groupedCalendar = function groupedCalendarWithAvailability(data, range) {
  const days = [];
  for (let iso = range.dateFrom; iso <= range.dateTo; iso = addDays(iso, 1)) days.push(iso);
  return `<div class="week-list">${days.map((iso) => {
    const bookings = bookingsForDate(data, iso);
    return `<section class="panel week-day">
      <div class="panel-header calendar-week-heading">
        <button class="calendar-open-day" data-open-date="${iso}" type="button">
          <span>${escapeHtml(dateLabel(iso, { weekday: "long", day: "numeric", month: "short" }))}</span>
          ${calendarAvailabilityBadge(iso)}
        </button>
        <span class="muted small">${bookings.length}</span>
      </div>
      ${bookings.length ? `<div class="list">${bookings.map((item) => bookingCard(item, data.timezone)).join("")}</div>` : `<div class="empty compact">Записей нет</div>`}
    </section>`;
  }).join("")}</div>`;
};

monthPanel = function monthPanelWithAvailability(data, range) {
  const first = parseIsoDate(range.dateFrom);
  const leading = (first.getUTCDay() + 6) % 7;
  const cells = [];
  for (let index = 0; index < leading; index += 1) cells.push(null);
  for (let iso = range.dateFrom; iso <= range.dateTo; iso = addDays(iso, 1)) cells.push(iso);
  return `<div class="month-panel panel">
    <div class="month-weekdays">${["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => `<span>${day}</span>`).join("")}</div>
    <div class="month-grid">${cells.map((iso) => {
      if (!iso) return '<span class="month-cell empty-cell"></span>';
      const bookings = bookingsForDate(data, iso);
      const status = calendarDayStatus(iso);
      return `<button class="month-cell ${status.off ? "is-day-off" : ""} ${iso === todayInTimezone(state.timezone) ? "today-cell" : ""}" data-open-date="${iso}" type="button">
        <strong>${escapeHtml(dateLabel(iso, { day: "numeric" }))}</strong>
        ${status.off ? '<span class="calendar-day-off">Выходной</span>' : `<span>${bookings.length ? `${bookings.length} запис.` : "—"}</span>`}
        ${bookings.slice(0, 2).map((booking) => `<small>${escapeHtml(booking.client_name)}</small>`).join("")}
      </button>`;
    }).join("")}</div>
  </div>`;
};

function closeCalendarAvailabilityDialog() {
  document.querySelector(".calendar-availability-backdrop")?.remove();
}

function calendarAvailabilityDialog(iso, title) {
  closeCalendarAvailabilityDialog();
  const backdrop = document.createElement("div");
  backdrop.className = "calendar-availability-backdrop";
  backdrop.innerHTML = `<section class="panel calendar-availability-dialog" role="dialog" aria-modal="true" aria-labelledby="calendar-availability-title">
    <div class="calendar-availability-heading">
      <div><p class="eyebrow">${escapeHtml(dateLabel(iso, { weekday: "long", day: "numeric", month: "long" }))}</p><h2 id="calendar-availability-title">${escapeHtml(title)}</h2></div>
      <button class="ghost-button calendar-availability-close" type="button" aria-label="Закрыть">×</button>
    </div>
    <div data-calendar-availability-body></div>
  </section>`;
  document.body.append(backdrop);
  backdrop.querySelector(".calendar-availability-close")?.addEventListener("click", closeCalendarAvailabilityDialog);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) closeCalendarAvailabilityDialog();
  });
  return backdrop.querySelector("[data-calendar-availability-body]");
}

function calendarExceptionPayload(iso, mode, startTime = null, endTime = null) {
  if (mode === "off") {
    return { days: [{ day: iso, state: "unavailable", intervals: [], note: "Выходной" }] };
  }
  return {
    days: [{
      day: iso,
      state: "available",
      intervals: [{ start_time: startTime, end_time: endTime }],
      note: null,
    }],
  };
}

function calendarConflictTime(value) {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: state.timezone,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

async function previewCalendarException(body, payload, successText) {
  body.innerHTML = '<p class="muted">Проверяем записи на этот день…</p>';
  try {
    const preview = await api("/web/api/schedule/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const day = (preview.days || [])[0];
    if (!day) throw new Error("preview_missing_day");
    const conflicts = day.conflicts || [];
    body.innerHTML = `
      <div class="calendar-preview-result ${day.can_apply ? "can-apply" : "blocked"}">
        <strong>${day.can_apply ? escapeHtml(successText) : "Сохранить выходной нельзя"}</strong>
        ${conflicts.length ? `<p class="muted">Мешает существующая запись:</p><div class="calendar-conflicts">${conflicts.map((item) => `
          <div class="calendar-conflict">
            <strong>${escapeHtml(item.client_public_name)}</strong>
            <span>${escapeHtml(item.service_name)}</span>
            <span>${escapeHtml(calendarConflictTime(item.starts_at))}–${escapeHtml(calendarConflictTime(item.ends_at))}</span>
          </div>`).join("")}</div>` : '<p class="muted">Конфликтов с существующими записями нет.</p>'}
      </div>
      <div class="calendar-availability-actions">
        ${day.can_apply ? '<button class="primary-button" type="button" data-apply-calendar-exception>Сохранить</button>' : ""}
        <button class="secondary-button" type="button" data-cancel-calendar-exception>Отмена</button>
      </div>
      <p class="booking-edit-error" role="alert"></p>`;
    body.querySelector("[data-cancel-calendar-exception]")?.addEventListener("click", closeCalendarAvailabilityDialog);
    body.querySelector("[data-apply-calendar-exception]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const errorLine = body.querySelector(".booking-edit-error");
      button.disabled = true;
      errorLine.textContent = "";
      try {
        await api("/web/api/schedule", {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        closeCalendarAvailabilityDialog();
        renderCalendar();
      } catch (error) {
        if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
        errorLine.textContent = error.message === "availability_conflicts_with_bookings"
          ? "Пока вы проверяли изменения, на этот день появилась запись. Обновите день и попробуйте снова."
          : "Не удалось сохранить изменение. Попробуйте ещё раз.";
        button.disabled = false;
      }
    });
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    body.innerHTML = '<p class="booking-edit-error" role="alert">Не удалось проверить изменение. Ничего не сохранено.</p><button class="secondary-button" type="button" data-cancel-calendar-exception>Закрыть</button>';
    body.querySelector("[data-cancel-calendar-exception]")?.addEventListener("click", closeCalendarAvailabilityDialog);
  }
}

async function openCalendarDayOff(iso) {
  const body = calendarAvailabilityDialog(iso, "Не работаю в этот день");
  const payload = calendarExceptionPayload(iso, "off");
  await previewCalendarException(body, payload, "День можно отметить выходным");
}

async function defaultCalendarHours(iso) {
  const current = calendarScheduleDay(iso);
  const interval = (current?.availability || []).find((item) => item.is_available);
  if (interval) {
    return {
      start: calendarAvailabilityTime(interval.start_time),
      end: calendarAvailabilityTime(interval.end_time),
    };
  }
  const preferences = await api("/web/api/schedule/default-work-hours");
  const usual = (preferences.default_work_intervals || [])[0] || {};
  return {
    start: calendarAvailabilityTime(usual.start_time),
    end: calendarAvailabilityTime(usual.end_time),
  };
}

async function openCalendarOtherHours(iso) {
  const body = calendarAvailabilityDialog(iso, "Другое время в этот день");
  body.innerHTML = '<p class="muted">Загружаем текущее рабочее время…</p>';
  try {
    const hours = await defaultCalendarHours(iso);
    body.innerHTML = `<form class="calendar-hours-form">
      <div class="calendar-hours-fields">
        <label><span>Начало</span><input type="time" name="start_time" required value="${escapeHtml(hours.start)}"></label>
        <label><span>Конец</span><input type="time" name="end_time" required value="${escapeHtml(hours.end)}"></label>
      </div>
      <p class="muted small">Сначала Нэйли проверит изменение и покажет, что произойдёт. Существующие записи не переносятся и не отменяются.</p>
      <p class="booking-edit-error" role="alert"></p>
      <div class="calendar-availability-actions">
        <button class="primary-button" type="submit">Проверить изменения</button>
        <button class="secondary-button" type="button" data-cancel-calendar-exception>Отмена</button>
      </div>
    </form>`;
    const form = body.querySelector("form");
    body.querySelector("[data-cancel-calendar-exception]")?.addEventListener("click", closeCalendarAvailabilityDialog);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const startTime = form.elements.start_time.value;
      const endTime = form.elements.end_time.value;
      const errorLine = form.querySelector(".booking-edit-error");
      errorLine.textContent = "";
      if (!startTime || !endTime || startTime >= endTime) {
        errorLine.textContent = "Время окончания должно быть позже времени начала.";
        return;
      }
      await previewCalendarException(
        body,
        calendarExceptionPayload(iso, "hours", startTime, endTime),
        `Рабочее время будет ${startTime}–${endTime}`,
      );
    });
    form.elements.start_time.focus();
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    body.innerHTML = '<p class="booking-edit-error" role="alert">Не удалось загрузить рабочее время.</p><button class="secondary-button" type="button" data-cancel-calendar-exception>Закрыть</button>';
    body.querySelector("[data-cancel-calendar-exception]")?.addEventListener("click", closeCalendarAvailabilityDialog);
  }
}

function bindCalendarAvailabilityControls() {
  document.querySelector("[data-day-off]")?.addEventListener("click", (event) => openCalendarDayOff(event.currentTarget.dataset.dayOff));
  document.querySelector("[data-day-hours]")?.addEventListener("click", (event) => openCalendarOtherHours(event.currentTarget.dataset.dayHours));
}

const bindCalendarControlsBeforeAvailability = bindCalendarControls;
bindCalendarControls = function bindCalendarControlsWithAvailability() {
  bindCalendarControlsBeforeAvailability();
  bindCalendarAvailabilityControls();
};

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.querySelector(".calendar-availability-backdrop")) {
    closeCalendarAvailabilityDialog();
  }
});
