function bookingConflictDateTime(value) {
  const date = new Date(value);
  return {
    date: new Intl.DateTimeFormat("ru-RU", {
      timeZone: APP_TIMEZONE,
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(date),
    time: new Intl.DateTimeFormat("ru-RU", {
      timeZone: APP_TIMEZONE,
      hour: "2-digit",
      minute: "2-digit",
    }).format(date),
  };
}

function bookingConflictMessage(error) {
  const conflicts = Array.isArray(error.details?.conflicts)
    ? error.details.conflicts
    : [];
  if (!conflicts.length) return "Это время пересекается с другой записью.";

  const heading = conflicts.length === 1
    ? "Выбранное время пересекается с записью:"
    : `Выбранное время пересекается с ${conflicts.length} записями:`;
  const lines = [heading];

  conflicts.forEach((conflict, index) => {
    const start = bookingConflictDateTime(conflict.starts_at);
    const end = bookingConflictDateTime(conflict.ends_at);
    const reservedStart = bookingConflictDateTime(conflict.reserved_starts_at);
    const reservedEnd = bookingConflictDateTime(conflict.reserved_ends_at);
    const addons = Array.isArray(conflict.addon_names) && conflict.addon_names.length
      ? ` + ${conflict.addon_names.join(", ")}`
      : "";
    const actualInterval = `${start.date}, ${start.time}–${end.time}`;
    const hasReservedDifference = new Date(conflict.reserved_starts_at).getTime() !== new Date(conflict.starts_at).getTime()
      || new Date(conflict.reserved_ends_at).getTime() !== new Date(conflict.ends_at).getTime();

    lines.push("");
    if (conflicts.length > 1) lines.push(`${index + 1}.`);
    lines.push(`Клиентка: ${conflict.client_name}`);
    lines.push(`Процедура: ${conflict.service_name}${addons}`);
    lines.push(`Запись: ${actualInterval}`);
    if (hasReservedDifference) {
      const reservedDate = reservedStart.date === reservedEnd.date
        ? reservedStart.date
        : `${reservedStart.date} — ${reservedEnd.date}`;
      lines.push(`С учётом времени до/после занято: ${reservedDate}, ${reservedStart.time}–${reservedEnd.time}`);
    }
  });

  return lines.join("\n");
}

async function bookingMutationApi(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status === 401) {
    const error = new Error("unauthorized");
    error.status = 401;
    throw error;
  }
  if (!response.ok) {
    let code = `http_${response.status}`;
    let details = null;
    try {
      const payload = await response.json();
      code = payload?.detail?.code || code;
      details = payload?.detail?.details || null;
    } catch {}
    const error = new Error(code);
    error.status = response.status;
    error.details = details;
    throw error;
  }
  return response.json();
}

const originalDetailedBookingErrorMessage = bookingErrorMessage;
bookingErrorMessage = function detailedBookingErrorMessage(error) {
  if (error.message === "booking_overlap") return bookingConflictMessage(error);
  return originalDetailedBookingErrorMessage(error);
};

submitBookingComposer = async function detailedSubmitBookingComposer(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = bookingPayload(form);
  if (!payload.body.client_public_name || !payload.body.service_name || !payload.day || !payload.time) {
    return window.alert("Выберите клиентку, процедуру, дату и время.");
  }

  const duration = bookingEstimatedDuration(
    payload.base,
    payload.addons,
    form.elements.duration_override_minutes.value,
  );
  const price = bookingEstimatedPrice(
    [payload.base, ...payload.addons].filter(Boolean),
    form.elements.price_override_amount.value,
  );
  const addons = payload.addons.length
    ? payload.addons.map((addon) => addon.public_name).join(", ")
    : "без дополнений";
  const confirmation = [
    `Клиентка: ${payload.body.client_public_name}`,
    `Процедура: ${payload.body.service_name}`,
    `Дополнения: ${addons}`,
    `Когда: ${payload.day}, ${payload.time}`,
    `Время: ${bookingDurationLabel(duration)}`,
    `Цена: ${price}`,
    "",
    "Создать запись?",
  ].join("\n");
  if (!window.confirm(confirmation)) return;

  const button = document.querySelector("#submit-booking-create");
  button.disabled = true;
  button.textContent = "Записываем…";
  try {
    const result = await bookingMutationApi("/web/api/bookings", {
      method: "POST",
      body: JSON.stringify(payload.body),
    });
    if (!bookingResultMatches(result, payload)) throw new Error("unverified_booking");
    bookingComposerOpen = false;
    bookingComposerData = null;
    bookingComposerIdempotencyKey = null;
    state.selectedDate = payload.day;
    state.calendarMode = "day";
    bookingComposerMessage = result.created
      ? "Запись создана и проверена."
      : "Такая запись уже была создана — показываем её в календаре.";
    await renderCalendar();
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    window.alert(bookingErrorMessage(error));
    button.disabled = false;
    button.textContent = "Проверить и записать";
  }
};
