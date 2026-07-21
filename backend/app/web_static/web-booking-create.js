let bookingComposerOpen = false;
let bookingComposerData = null;
let bookingComposerIdempotencyKey = null;
let bookingComposerMessage = "";

function bookingIdempotencyKey() {
  if (window.crypto?.randomUUID) return `web-${window.crypto.randomUUID()}`;
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function bookingGroupedOptions(services) {
  const groups = new Map();
  services.forEach((service) => {
    const category = String(service.category || "").trim() || "Без раздела";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push(service);
  });
  return [...groups.entries()].map(([category, items]) => `
    <optgroup label="${escapeHtml(category)}">
      ${items.map((service) => `<option value="${escapeHtml(service.public_name)}">${escapeHtml(service.public_name)}</option>`).join("")}
    </optgroup>`).join("");
}

function bookingAddonChoices(services) {
  if (!services.length) return '<p class="muted small">Дополнений в прайсе пока нет.</p>';
  const groups = new Map();
  services.forEach((service) => {
    const category = String(service.category || "").trim() || "Дополнительно";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push(service);
  });
  return [...groups.entries()].map(([category, items]) => `
    <fieldset class="booking-addon-group">
      <legend>${escapeHtml(category)}</legend>
      ${items.map((service) => `<label class="booking-addon">
        <input type="checkbox" name="addon_names" value="${escapeHtml(service.public_name)}">
        <span><strong>${escapeHtml(service.public_name)}</strong><small>${escapeHtml(bookingServicePrice(service))}${service.extra_minutes ? ` · +${escapeHtml(service.extra_minutes)} мин` : ""}</small></span>
      </label>`).join("")}
    </fieldset>`).join("");
}

function bookingServicePrice(service) {
  const money = (value) => `${Number(value || 0).toLocaleString("ru-RU")} ₽`;
  if (service.price_type === "range") {
    return `${money(service.price_min_amount)}–${money(service.price_max_amount)}`;
  }
  if (service.price_type === "per_unit") {
    return `${money(service.price_amount)}${service.price_unit ? ` / ${service.price_unit}` : " за единицу"}`;
  }
  if (service.price_type === "on_request") return "цена после уточнения";
  return money(service.price_amount);
}

function bookingSelectedServices(form) {
  const active = bookingComposerData?.services || [];
  const base = active.find((service) => service.public_name === form.elements.service_name.value);
  const addonNames = [...form.querySelectorAll('input[name="addon_names"]:checked')].map((input) => input.value);
  const addons = addonNames.map((name) => active.find((service) => service.public_name === name)).filter(Boolean);
  return { base, addons };
}

function bookingEstimatedPrice(services, overrideValue = "") {
  if (overrideValue !== "") return `${Number(overrideValue).toLocaleString("ru-RU")} ₽ — указано для этой записи`;
  if (!services.length) return "Выберите процедуру";

  let fixed = 0;
  let minimum = 0;
  let maximum = 0;
  const unitParts = [];
  let asks = false;
  let hasRange = false;

  services.forEach((service) => {
    if (service.price_type === "fixed") {
      fixed += Number(service.price_amount || 0);
      minimum += Number(service.price_amount || 0);
      maximum += Number(service.price_amount || 0);
    } else if (service.price_type === "range") {
      hasRange = true;
      minimum += Number(service.price_min_amount || 0);
      maximum += Number(service.price_max_amount || 0);
    } else if (service.price_type === "per_unit") {
      unitParts.push(bookingServicePrice(service));
    } else {
      asks = true;
    }
  });

  if (asks) return "Цена после уточнения";
  if (unitParts.length) {
    const fixedPart = fixed ? `${fixed.toLocaleString("ru-RU")} ₽ + ` : "";
    return `${fixedPart}${unitParts.join(" + ")} · итог после уточнения`;
  }
  if (hasRange) return `${minimum.toLocaleString("ru-RU")}–${maximum.toLocaleString("ru-RU")} ₽`;
  return `${fixed.toLocaleString("ru-RU")} ₽`;
}

function bookingEstimatedDuration(base, addons, overrideValue = "") {
  if (overrideValue !== "") return Number(overrideValue);
  if (!base) return 0;
  return Number(base.duration_minutes || 0) + addons.reduce((sum, addon) => sum + Number(addon.extra_minutes || 0), 0);
}

function bookingDurationLabel(minutes) {
  if (!minutes) return "Время не указано";
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (!hours) return `${remainder} мин`;
  return remainder ? `${hours} ч ${remainder} мин` : `${hours} ч`;
}

function updateBookingComposerSummary() {
  const form = document.querySelector("#booking-create-form");
  const summary = document.querySelector("#booking-create-summary");
  if (!form || !summary) return;
  const { base, addons } = bookingSelectedServices(form);
  const duration = bookingEstimatedDuration(base, addons, form.elements.duration_override_minutes.value);
  const price = bookingEstimatedPrice([base, ...addons].filter(Boolean), form.elements.price_override_amount.value);
  const addonText = addons.length ? addons.map((addon) => addon.public_name).join(", ") : "без дополнений";
  summary.innerHTML = `
    <strong>${escapeHtml(base?.public_name || "Выберите основную процедуру")}</strong>
    <span>${escapeHtml(addonText)}</span>
    <span>${escapeHtml(bookingDurationLabel(duration))} · ${escapeHtml(price)}</span>`;
}

function renderBookingComposer() {
  const content = document.querySelector("#page-content");
  if (!content || !bookingComposerData) return;

  document.querySelector("#booking-composer")?.remove();
  const clients = bookingComposerData.clients.filter((client) => client.profile_status === "active");
  const services = bookingComposerData.services.filter((service) => service.is_active);
  const bases = services.filter((service) => service.kind === "base");
  const addons = services.filter((service) => service.kind === "addon");

  content.insertAdjacentHTML("afterbegin", `
    <section id="booking-composer" class="panel booking-composer">
      <div class="panel-header">
        <div><p class="eyebrow">Новая запись</p><h2>Кого и на что записать?</h2></div>
        <button id="close-booking-composer" class="ghost-button" type="button">Закрыть</button>
      </div>
      <form id="booking-create-form" class="booking-form">
        <label class="catalog-field"><span>Клиентка</span>
          <select name="client_public_name" required>
            <option value="">Выберите клиентку</option>
            ${clients.map((client) => `<option value="${escapeHtml(client.public_name)}">${escapeHtml(client.public_name)}</option>`).join("")}
          </select>
        </label>
        <label class="catalog-field"><span>Дата</span>
          <input name="day" type="date" value="${escapeHtml(state.selectedDate)}" required>
        </label>
        <label class="catalog-field"><span>Время</span>
          <input name="time" type="time" value="11:00" required>
        </label>
        <label class="catalog-field booking-base-field"><span>Основная процедура</span>
          <select name="service_name" required>
            <option value="">Выберите из прайса</option>
            ${bookingGroupedOptions(bases)}
          </select>
        </label>
        <div class="booking-addons">
          <span class="booking-field-title">Дополнения <em>необязательно</em></span>
          ${bookingAddonChoices(addons)}
        </div>
        <details class="booking-overrides">
          <summary>Уточнить цену или время для этой записи</summary>
          <div class="booking-override-grid">
            <label class="catalog-field"><span>Итоговая цена, ₽ <em>необязательно</em></span>
              <input name="price_override_amount" type="number" min="0" step="1" placeholder="Оставьте пустым для цены из прайса">
            </label>
            <label class="catalog-field"><span>Итоговое время, мин <em>необязательно</em></span>
              <input name="duration_override_minutes" type="number" min="1" max="1440" step="1" placeholder="Оставьте пустым для обычного времени">
            </label>
          </div>
        </details>
        <div id="booking-create-summary" class="booking-create-summary" aria-live="polite"></div>
        ${!clients.length ? '<div class="info-note">Сначала добавьте клиентку через Нэйли — после этого она появится здесь.</div>' : ""}
        ${!bases.length ? '<div class="info-note">В прайсе пока нет основной процедуры. Добавьте её в разделе «Мой прайс».</div>' : ""}
        <div class="booking-form-actions">
          <button id="cancel-booking-create" class="secondary-button" type="button">Отмена</button>
          <button id="submit-booking-create" class="primary-button" type="submit" ${!clients.length || !bases.length ? "disabled" : ""}>Проверить и записать</button>
        </div>
      </form>
    </section>`);

  const form = document.querySelector("#booking-create-form");
  form.addEventListener("input", () => {
    bookingComposerIdempotencyKey = bookingIdempotencyKey();
    updateBookingComposerSummary();
  });
  form.addEventListener("change", updateBookingComposerSummary);
  form.addEventListener("submit", submitBookingComposer);
  document.querySelector("#close-booking-composer").addEventListener("click", closeBookingComposer);
  document.querySelector("#cancel-booking-create").addEventListener("click", closeBookingComposer);
  updateBookingComposerSummary();
  document.querySelector("#booking-composer").scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeBookingComposer() {
  bookingComposerOpen = false;
  bookingComposerData = null;
  bookingComposerIdempotencyKey = null;
  document.querySelector("#booking-composer")?.remove();
}

async function openBookingComposer() {
  bookingComposerOpen = true;
  bookingComposerIdempotencyKey ||= bookingIdempotencyKey();
  const button = document.querySelector("#open-booking-composer");
  if (button) {
    button.disabled = true;
    button.textContent = "Загружаем…";
  }
  try {
    const [clients, services] = await Promise.all([
      api("/web/api/clients"),
      api("/web/api/services"),
    ]);
    bookingComposerData = { clients: clients.clients, services: services.services };
    renderBookingComposer();
  } catch (error) {
    bookingComposerOpen = false;
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    window.alert("Не удалось подготовить новую запись. Попробуйте ещё раз.");
  } finally {
    if (button?.isConnected) {
      button.disabled = false;
      button.textContent = "Добавить запись";
    }
  }
}

function bookingPayload(form) {
  const { base, addons } = bookingSelectedServices(form);
  const day = form.elements.day.value;
  const time = form.elements.time.value;
  const priceOverride = form.elements.price_override_amount.value;
  const durationOverride = form.elements.duration_override_minutes.value;
  return {
    body: {
      client_public_name: form.elements.client_public_name.value,
      service_name: base?.public_name || "",
      addon_names: addons.map((addon) => addon.public_name),
      starts_at: `${day}T${time}:00+03:00`,
      price_override_amount: priceOverride === "" ? null : Number(priceOverride),
      duration_override_minutes: durationOverride === "" ? null : Number(durationOverride),
      idempotency_key: bookingComposerIdempotencyKey || bookingIdempotencyKey(),
    },
    day,
    time,
    base,
    addons,
  };
}

function bookingResultMatches(result, payload) {
  const booking = result?.booking;
  if (!booking) return false;
  const actualAddons = [...(booking.addon_names || [])].sort((left, right) => left.localeCompare(right, "ru"));
  const expectedAddons = [...payload.body.addon_names].sort((left, right) => left.localeCompare(right, "ru"));
  return booking.client_name === payload.body.client_public_name
    && booking.service_name === payload.body.service_name
    && JSON.stringify(actualAddons) === JSON.stringify(expectedAddons)
    && new Date(booking.starts_at).getTime() === new Date(payload.body.starts_at).getTime();
}

function bookingErrorMessage(error) {
  const messages = {
    booking_overlap: "Это время пересекается с другой записью.",
    booking_on_day_off: "Этот день отмечен как выходной.",
    client_not_found: "Клиентка больше не найдена. Обновите форму.",
    service_not_found: "Процедура больше не входит в прайс. Обновите форму.",
    addon_not_found: "Одно из дополнений больше не входит в прайс. Обновите форму.",
    idempotency_conflict: "Состав записи изменился во время повторной отправки. Закройте форму и создайте запись заново.",
  };
  return messages[error.message] || "Не удалось создать запись. Проверьте данные и попробуйте ещё раз.";
}

async function submitBookingComposer(event) {
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
  const addons = payload.addons.length ? payload.addons.map((addon) => addon.public_name).join(", ") : "без дополнений";
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
    const result = await api("/web/api/bookings", {
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
}

function bookingCalendarPrice(booking) {
  if (booking.price_amount !== null && booking.price_amount !== undefined) {
    return formatMoney(booking.price_amount, booking.currency);
  }
  if (
    booking.price_type === "range"
    && booking.price_min_amount !== null
    && booking.price_max_amount !== null
  ) {
    return `${Number(booking.price_min_amount).toLocaleString("ru-RU")}–${Number(booking.price_max_amount).toLocaleString("ru-RU")} ₽`;
  }
  if (booking.price_type === "per_unit") {
    const amount = booking.price_min_amount ?? booking.price_max_amount;
    return amount === null || amount === undefined
      ? "Цена по факту"
      : `${Number(amount).toLocaleString("ru-RU")} ₽${booking.price_unit ? ` / ${booking.price_unit}` : ""}`;
  }
  return "Цена уточняется";
}

bookingCard = function bookingComposerCard(booking, timezone) {
  const start = new Date(booking.starts_at);
  const end = new Date(booking.ends_at);
  const format = new Intl.DateTimeFormat("ru-RU", { timeZone: timezone, hour: "2-digit", minute: "2-digit" });
  const addons = booking.addon_names?.length ? ` + ${booking.addon_names.join(", ")}` : "";
  return `<article class="booking">
    <div class="time">${escapeHtml(format.format(start))}</div>
    <div><h3>${escapeHtml(booking.client_name)}</h3><p>${escapeHtml(booking.service_name)}${escapeHtml(addons)} · до ${escapeHtml(format.format(end))}</p><span class="badge">${escapeHtml(booking.status)}</span></div>
    <div class="price">${escapeHtml(bookingCalendarPrice(booking))}</div>
  </article>`;
};

const originalBookingAppShell = appShell;
appShell = function bookingComposerAppShell(title, body) {
  originalBookingAppShell(title, body);
  const eyebrow = document.querySelector(".topbar .eyebrow");
  if (eyebrow) eyebrow.textContent = "кабинет мастера";
};

const originalBookingRenderCalendar = renderCalendar;
renderCalendar = async function bookingComposerRenderCalendar() {
  await originalBookingRenderCalendar();
  if (state.view !== "calendar") return;

  const actions = document.querySelector("#page-actions");
  if (actions && !actions.querySelector("#open-booking-composer")) {
    const button = document.createElement("button");
    button.id = "open-booking-composer";
    button.className = "primary-button compact-primary";
    button.type = "button";
    button.textContent = "Добавить запись";
    button.addEventListener("click", openBookingComposer);
    actions.prepend(button);
  }

  if (bookingComposerMessage) {
    const content = document.querySelector("#page-content");
    content?.insertAdjacentHTML("afterbegin", `<div class="info-note" role="status">${escapeHtml(bookingComposerMessage)}</div>`);
    bookingComposerMessage = "";
  }
  if (bookingComposerOpen) {
    if (bookingComposerData) renderBookingComposer();
    else await openBookingComposer();
  }
};
