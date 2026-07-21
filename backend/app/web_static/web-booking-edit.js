const bookingCardWithoutEditing = bookingCard;

function bookingCanChange(booking) {
  return booking.status === "scheduled" && new Date(booking.starts_at).getTime() > Date.now();
}

function bookingEditPayload(booking) {
  return encodeURIComponent(JSON.stringify({
    client_public_name: booking.client_name,
    service_name: booking.service_name,
    starts_at: booking.starts_at,
    ends_at: booking.ends_at,
    status: booking.status,
  }));
}

bookingCard = function editableBookingCard(booking, timezone) {
  const card = bookingCardWithoutEditing(booking, timezone);
  if (!bookingCanChange(booking)) return card;
  return card.replace(
    '<article class="booking">',
    `<article class="booking booking-editable" role="button" tabindex="0" data-edit-booking="${bookingEditPayload(booking)}" aria-label="Открыть запись ${escapeHtml(booking.client_name)}">`,
  ).replace("</article>", '<span class="booking-edit-hint">Открыть</span></article>');
};

function localInputValue(iso) {
  const date = new Date(iso);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: APP_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}T${value.hour}:${value.minute}`;
}

function moscowIso(localValue) {
  return `${localValue}:00+03:00`;
}

function bookingErrorText(error) {
  const messages = {
    booking_not_found: "Запись не найдена или принадлежит другому мастеру.",
    booking_not_active: "Эту запись уже нельзя изменить.",
    booking_already_cancelled: "Запись уже отменена.",
    booking_already_completed: "Завершённую запись нельзя перенести или отменить.",
    booking_overlap: "Новое время пересекается с другой записью.",
    availability_closed: "В этот день мастер не работает.",
    outside_availability: "Новое время находится вне рабочего времени.",
    invalid_booking_time: "Проверьте выбранные дату и время.",
  };
  return messages[error.message] || "Не удалось изменить запись. Проверьте время и попробуйте снова.";
}

function closeBookingDialog() {
  document.querySelector("#booking-edit-dialog")?.remove();
}

function openBookingDialog(booking) {
  closeBookingDialog();
  const dialog = document.createElement("dialog");
  dialog.id = "booking-edit-dialog";
  dialog.className = "booking-edit-dialog";
  dialog.innerHTML = `
    <form method="dialog" class="booking-edit-card">
      <div class="booking-edit-header">
        <div><p class="eyebrow">Запись</p><h2>${escapeHtml(booking.client_public_name)}</h2></div>
        <button class="ghost-button" value="close" aria-label="Закрыть" type="submit">×</button>
      </div>
      <p class="muted">${escapeHtml(booking.service_name)}</p>
      <label class="booking-edit-field">Новая дата и время
        <input id="booking-new-start" type="datetime-local" value="${localInputValue(booking.starts_at)}" required />
      </label>
      <p id="booking-edit-error" class="booking-edit-error" role="alert"></p>
      <div class="booking-edit-actions">
        <button id="booking-reschedule" class="primary-button" type="button">Перенести</button>
        <button id="booking-cancel" class="danger-button" type="button">Отменить запись</button>
      </div>
    </form>`;
  document.body.append(dialog);
  dialog.addEventListener("close", closeBookingDialog);
  dialog.showModal();

  document.querySelector("#booking-reschedule").addEventListener("click", async () => {
    const button = document.querySelector("#booking-reschedule");
    const errorLine = document.querySelector("#booking-edit-error");
    const localValue = document.querySelector("#booking-new-start").value;
    if (!localValue) return;
    button.disabled = true;
    errorLine.textContent = "";
    try {
      await api("/web/api/bookings/reschedule", {
        method: "PUT",
        body: JSON.stringify({
          client_public_name: booking.client_public_name,
          service_name: booking.service_name,
          starts_at: booking.starts_at,
          new_starts_at: moscowIso(localValue),
        }),
      });
      closeBookingDialog();
      await renderCalendar();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = bookingErrorText(error);
      button.disabled = false;
    }
  });

  document.querySelector("#booking-cancel").addEventListener("click", async () => {
    if (!window.confirm(`Отменить запись ${booking.client_public_name}? История записи сохранится.`)) return;
    const button = document.querySelector("#booking-cancel");
    const errorLine = document.querySelector("#booking-edit-error");
    button.disabled = true;
    errorLine.textContent = "";
    try {
      await api("/web/api/bookings/cancel", {
        method: "PUT",
        body: JSON.stringify({
          client_public_name: booking.client_public_name,
          service_name: booking.service_name,
          starts_at: booking.starts_at,
        }),
      });
      closeBookingDialog();
      await renderCalendar();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = bookingErrorText(error);
      button.disabled = false;
    }
  });
}

function bindBookingEditing() {
  document.querySelectorAll("[data-edit-booking]").forEach((card) => {
    const open = () => openBookingDialog(JSON.parse(decodeURIComponent(card.dataset.editBooking)));
    card.addEventListener("click", open);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

const renderCalendarWithoutBookingEditing = renderCalendar;
renderCalendar = async function renderEditableCalendar() {
  await renderCalendarWithoutBookingEditing();
  bindBookingEditing();
};
