const bookingCardWithoutEditing = bookingCard;
let bookingEditData = null;

function bookingCanChange(booking) {
  return booking.status === "scheduled" || booking.status === "completed";
}

function bookingEditPayload(booking) {
  return encodeURIComponent(JSON.stringify({
    booking_id: booking.booking_id,
    client_public_name: booking.client_name,
    service_name: booking.service_name,
    addon_names: booking.addon_names || [],
    starts_at: booking.starts_at,
    ends_at: booking.ends_at,
    status: booking.status,
    price_amount: booking.price_amount,
    price_type: booking.price_type,
    price_confirmed: booking.price_confirmed,
    duration_minutes: booking.duration_minutes,
  }));
}

function bookingStatusLabel(status) {
  const labels = {
    cancelled: "Отменена",
    completed: "Визит состоялся",
    no_show: "Не пришла",
  };
  return labels[status] || "";
}

bookingCard = function editableBookingCard(booking, timezone) {
  let card = bookingCardWithoutEditing(booking, timezone);
  const statusLabel = bookingStatusLabel(booking.status);
  card = card.replace(
    `<span class="badge">${escapeHtml(booking.status)}</span>`,
    statusLabel ? `<span class="badge">${escapeHtml(statusLabel)}</span>` : "",
  );
  if (!bookingCanChange(booking)) return card;
  return card.replace(
    '<article class="booking">',
    `<article class="booking booking-editable" role="button" tabindex="0" data-edit-booking="${bookingEditPayload(booking)}" aria-label="Изменить запись ${escapeHtml(booking.client_name)}">`,
  ).replace("</article>", '<span class="booking-edit-hint">Изменить</span></article>');
};

function localBookingParts(iso) {
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
  return { day: `${value.year}-${value.month}-${value.day}`, time: `${value.hour}:${value.minute}` };
}

function bookingTimeOptions(selected = "11:00") {
  const values = [];
  for (let minutes = 0; minutes < 24 * 60; minutes += 15) {
    const hours = String(Math.floor(minutes / 60)).padStart(2, "0");
    const mins = String(minutes % 60).padStart(2, "0");
    const value = `${hours}:${mins}`;
    values.push(`<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`);
  }
  return values.join("");
}

function bookingErrorText(error) {
  const messages = {
    booking_not_found: "Запись не найдена или принадлежит другому мастеру.",
    booking_not_editable: "Эту запись уже нельзя изменить.",
    booking_overlap: "Новое время пересекается с другой записью.",
    booking_on_day_off: "В этот день указан выходной.",
    service_not_found: "Процедура больше не доступна в прайсе.",
    addon_not_found: "Одно из дополнений больше не доступно в прайсе.",
    client_not_found: "Карточка клиентки больше не доступна.",
  };
  return messages[error.message] || "Не удалось изменить запись. Проверьте данные и попробуйте снова.";
}

function closeBookingDialog() {
  document.querySelector("#booking-edit-dialog")?.remove();
  bookingEditData = null;
}

function selectedEditServices(form) {
  const services = bookingEditData?.services || [];
  const base = services.find((service) => service.public_name === form.elements.service_name.value);
  const addonNames = [...form.querySelectorAll('input[name="addon_names"]:checked')].map((input) => input.value);
  const addons = addonNames.map((name) => services.find((service) => service.public_name === name)).filter(Boolean);
  return { base, addons };
}

function updateBookingEditSummary() {
  const form = document.querySelector("#booking-edit-form");
  const summary = document.querySelector("#booking-edit-summary");
  if (!form || !summary) return;
  const { base, addons } = selectedEditServices(form);
  const duration = bookingEstimatedDuration(base, addons, form.elements.duration_override_minutes.value);
  const price = bookingEstimatedPrice([base, ...addons].filter(Boolean), form.elements.price_override_amount.value);
  const addonText = addons.length ? addons.map((addon) => addon.public_name).join(", ") : "без дополнений";
  summary.innerHTML = `<strong>${escapeHtml(form.elements.client_public_name.value || "Клиентка")}</strong><span>${escapeHtml(base?.public_name || "Выберите процедуру")} · ${escapeHtml(addonText)}</span><span>${escapeHtml(form.elements.day.value)} ${escapeHtml(form.elements.time.value)} · ${escapeHtml(bookingDurationLabel(duration))} · ${escapeHtml(price)}</span>`;
}

function checkedAddonChoices(services, selectedNames) {
  const selected = new Set(selectedNames || []);
  if (!services.length) return '<p class="muted small">Дополнений в прайсе пока нет.</p>';
  return services.map((service) => `<label class="booking-addon"><input type="checkbox" name="addon_names" value="${escapeHtml(service.public_name)}" ${selected.has(service.public_name) ? "checked" : ""}><span><strong>${escapeHtml(service.public_name)}</strong><small>${escapeHtml(bookingServicePrice(service))}${service.extra_minutes ? ` · +${escapeHtml(service.extra_minutes)} мин` : ""}</small></span></label>`).join("");
}

function renderBookingDialog(booking) {
  const current = localBookingParts(booking.starts_at);
  const clients = bookingEditData.clients.filter((client) => client.profile_status === "active");
  const services = bookingEditData.services.filter((service) => service.is_active);
  const bases = services.filter((service) => service.kind === "base");
  const addons = services.filter((service) => service.kind === "addon");
  const dialog = document.createElement("dialog");
  dialog.id = "booking-edit-dialog";
  dialog.className = "booking-edit-dialog";
  dialog.innerHTML = `<form id="booking-edit-form" method="dialog" class="booking-edit-card booking-form">
    <div class="booking-edit-header"><div><p class="eyebrow">Запись</p><h2>Изменить запись</h2></div><button class="ghost-button" value="close" aria-label="Закрыть" type="submit">×</button></div>
    <label class="catalog-field"><span>Клиентка</span><select name="client_public_name" required>${clients.map((client) => `<option value="${escapeHtml(client.public_name)}" ${client.public_name === booking.client_public_name ? "selected" : ""}>${escapeHtml(client.public_name)}</option>`).join("")}</select></label>
    <div class="booking-edit-date-time"><label class="booking-edit-field">Дата<input name="day" type="date" value="${escapeHtml(current.day)}" required></label><label class="booking-edit-field">Время<select name="time" required>${bookingTimeOptions(current.time)}</select></label></div>
    <label class="catalog-field"><span>Основная процедура</span><select name="service_name" required>${bases.map((service) => `<option value="${escapeHtml(service.public_name)}" ${service.public_name === booking.service_name ? "selected" : ""}>${escapeHtml(service.public_name)}</option>`).join("")}</select></label>
    <div class="booking-addons"><span class="booking-field-title">Дополнения <em>необязательно</em></span>${checkedAddonChoices(addons, booking.addon_names)}</div>
    <details class="booking-overrides"><summary>Уточнить цену или время для этой записи</summary><div class="booking-override-grid"><label class="catalog-field"><span>Итоговая цена, ₽</span><input name="price_override_amount" type="number" min="0" step="1" placeholder="Автоматически из прайса"></label><label class="catalog-field"><span>Итоговое время, мин</span><input name="duration_override_minutes" type="number" min="1" max="1440" step="1" placeholder="Автоматически из прайса"></label></div></details>
    <div id="booking-edit-summary" class="booking-create-summary" aria-live="polite"></div><p id="booking-edit-error" class="booking-edit-error" role="alert"></p>
    <div class="booking-edit-actions"><button id="booking-save" class="primary-button" type="button">Проверить и сохранить</button>${booking.status === "scheduled" ? '<button id="booking-cancel" class="danger-button" type="button">Отменить запись</button>' : ""}</div>
  </form>`;
  document.body.append(dialog);
  dialog.addEventListener("close", closeBookingDialog);
  dialog.showModal();
  const form = document.querySelector("#booking-edit-form");
  form.addEventListener("input", updateBookingEditSummary);
  form.addEventListener("change", updateBookingEditSummary);
  updateBookingEditSummary();

  document.querySelector("#booking-save").addEventListener("click", async () => {
    const { base, addons: selectedAddons } = selectedEditServices(form);
    const priceValue = form.elements.price_override_amount.value;
    const durationValue = form.elements.duration_override_minutes.value;
    const body = { client_public_name: form.elements.client_public_name.value, service_name: base?.public_name || "", addon_names: selectedAddons.map((item) => item.public_name), starts_at: `${form.elements.day.value}T${form.elements.time.value}:00+03:00`, price_override_amount: priceValue === "" ? null : Number(priceValue), duration_override_minutes: durationValue === "" ? null : Number(durationValue) };
    const text = document.querySelector("#booking-edit-summary").innerText;
    if (!window.confirm(`Сохранить изменения?\n\n${text}`)) return;
    const button = document.querySelector("#booking-save");
    const errorLine = document.querySelector("#booking-edit-error");
    button.disabled = true;
    errorLine.textContent = "";
    try { await api(`/web/api/bookings/${booking.booking_id}`, { method: "PUT", body: JSON.stringify(body) }); closeBookingDialog(); await renderCalendar(); }
    catch (error) { if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова."); errorLine.textContent = bookingErrorText(error); button.disabled = false; }
  });

  document.querySelector("#booking-cancel")?.addEventListener("click", async () => {
    if (!window.confirm(`Отменить запись ${booking.client_public_name}? История сохранится.`)) return;
    try { await api("/web/api/bookings/cancel", { method: "PUT", body: JSON.stringify({ client_public_name: booking.client_public_name, service_name: booking.service_name, starts_at: booking.starts_at }) }); closeBookingDialog(); await renderCalendar(); }
    catch (error) { document.querySelector("#booking-edit-error").textContent = bookingErrorText(error); }
  });
}

async function openBookingDialog(booking) {
  closeBookingDialog();
  try {
    const [clients, services] = await Promise.all([api("/web/api/clients"), api("/web/api/services")]);
    bookingEditData = { clients: clients.clients, services: services.services };
    renderBookingDialog(booking);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    window.alert("Не удалось подготовить редактирование записи.");
  }
}

function bindBookingEditing() {
  document.querySelectorAll("[data-edit-booking]").forEach((card) => {
    const open = () => openBookingDialog(JSON.parse(decodeURIComponent(card.dataset.editBooking)));
    card.addEventListener("click", open);
    card.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } });
  });
}

const renderCalendarWithoutBookingEditing = renderCalendar;
renderCalendar = async function renderEditableCalendar() { await renderCalendarWithoutBookingEditing(); bindBookingEditing(); };
