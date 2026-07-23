function bookingQuantityInput(service, quantity = 1) {
  return `<label class="booking-addon-quantity">
    <span>Количество</span>
    <input type="number" min="1" max="100" step="1" value="${escapeHtml(quantity)}" data-addon-quantity="${escapeHtml(service.public_name)}" aria-label="Количество: ${escapeHtml(service.public_name)}">
  </label>`;
}

function bookingQuantityMap(form, addons) {
  const result = {};
  addons.forEach((addon) => {
    const input = [...form.querySelectorAll("[data-addon-quantity]")]
      .find((candidate) => candidate.dataset.addonQuantity === addon.public_name);
    const quantity = Number(input?.value || 1);
    if (Number.isInteger(quantity) && quantity > 1) result[addon.public_name] = quantity;
  });
  return result;
}

function bookingAddonLabel(addon, quantity = 1) {
  return quantity > 1 ? `${addon.public_name} × ${quantity}` : addon.public_name;
}

bookingAddonChoices = function quantityAddonChoices(services) {
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
      ${items.map((service) => `<div class="booking-addon-row">
        <label class="booking-addon">
          <input type="checkbox" name="addon_names" value="${escapeHtml(service.public_name)}">
          <span><strong>${escapeHtml(service.public_name)}</strong><small>${escapeHtml(bookingServicePrice(service))}${service.extra_minutes ? ` · +${escapeHtml(service.extra_minutes)} мин` : ""}</small></span>
        </label>
        ${bookingQuantityInput(service)}
      </div>`).join("")}
    </fieldset>`).join("");
};

checkedAddonChoices = function quantityCheckedAddonChoices(services, selectedNames, selectedQuantities = {}) {
  const selected = new Set(selectedNames || []);
  if (!services.length) return '<p class="muted small">Дополнений в прайсе пока нет.</p>';
  return services.map((service) => `<div class="booking-addon-row">
    <label class="booking-addon">
      <input type="checkbox" name="addon_names" value="${escapeHtml(service.public_name)}" ${selected.has(service.public_name) ? "checked" : ""}>
      <span><strong>${escapeHtml(service.public_name)}</strong><small>${escapeHtml(bookingServicePrice(service))}${service.extra_minutes ? ` · +${escapeHtml(service.extra_minutes)} мин` : ""}</small></span>
    </label>
    ${bookingQuantityInput(service, selectedQuantities[service.public_name] || 1)}
  </div>`).join("");
};

function bookingSelectedComposition(form, services) {
  const base = services.find((service) => service.public_name === form.elements.service_name.value);
  const addonNames = [...form.querySelectorAll('input[name="addon_names"]:checked')].map((input) => input.value);
  const addons = addonNames.map((name) => services.find((service) => service.public_name === name)).filter(Boolean);
  return { base, addons, quantities: bookingQuantityMap(form, addons) };
}

bookingSelectedServices = function quantitySelectedServices(form) {
  return bookingSelectedComposition(form, bookingComposerData?.services || []);
};

selectedEditServices = function quantitySelectedEditServices(form) {
  return bookingSelectedComposition(form, bookingEditData?.services || []);
};

const bookingPayloadWithoutQuantities = bookingPayload;
bookingPayload = function quantityBookingPayload(form) {
  const payload = bookingPayloadWithoutQuantities(form);
  const composition = bookingSelectedServices(form);
  payload.body.addon_quantities = composition.quantities;
  payload.quantities = composition.quantities;
  return payload;
};

const bookingResultMatchesWithoutQuantities = bookingResultMatches;
bookingResultMatches = function quantityBookingResultMatches(result, payload) {
  if (!bookingResultMatchesWithoutQuantities(result, payload)) return false;
  const items = result?.booking?.catalog_items || [];
  return payload.body.addon_names.every((name) => {
    const item = items.find((candidate) => candidate.kind === "addon" && candidate.public_name === name);
    return Number(item?.quantity || 1) === Number(payload.body.addon_quantities[name] || 1);
  });
};

const bookingEditPayloadWithoutQuantities = bookingEditPayload;
bookingEditPayload = function quantityBookingEditPayload(booking) {
  const raw = JSON.parse(decodeURIComponent(bookingEditPayloadWithoutQuantities(booking)));
  raw.addon_quantities = {};
  (booking.catalog_items || []).forEach((item) => {
    if (item.kind === "addon" && Number(item.quantity || 1) > 1) {
      raw.addon_quantities[item.public_name] = Number(item.quantity);
    }
  });
  return encodeURIComponent(JSON.stringify(raw));
};

const renderBookingDialogWithoutQuantities = renderBookingDialog;
renderBookingDialog = function quantityBookingDialog(booking) {
  renderBookingDialogWithoutQuantities(booking);
  const form = document.querySelector("#booking-edit-form");
  if (!form) return;
  Object.entries(booking.addon_quantities || {}).forEach(([name, quantity]) => {
    const input = [...form.querySelectorAll("[data-addon-quantity]")]
      .find((candidate) => candidate.dataset.addonQuantity === name);
    if (input) input.value = quantity;
  });
  const save = document.querySelector("#booking-save");
  const replacement = save?.cloneNode(true);
  if (!save || !replacement) return;
  save.replaceWith(replacement);
  replacement.addEventListener("click", async () => {
    const { base, addons, quantities } = selectedEditServices(form);
    const priceValue = form.elements.price_override_amount.value;
    const durationValue = form.elements.duration_override_minutes.value;
    const body = {
      client_public_name: form.elements.client_public_name.value,
      service_name: base?.public_name || "",
      addon_names: addons.map((item) => item.public_name),
      addon_quantities: quantities,
      starts_at: `${form.elements.day.value}T${form.elements.time.value}:00+03:00`,
      price_override_amount: priceValue === "" ? null : Number(priceValue),
      duration_override_minutes: durationValue === "" ? null : Number(durationValue),
    };
    const text = document.querySelector("#booking-edit-summary").innerText;
    if (!window.confirm(`Сохранить изменения?\n\n${text}`)) return;
    const errorLine = document.querySelector("#booking-edit-error");
    replacement.disabled = true;
    errorLine.textContent = "";
    try {
      await api(`/web/api/bookings/${booking.booking_id}`, { method: "PUT", body: JSON.stringify(body) });
      closeBookingDialog();
      await renderCalendar();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = bookingErrorText(error);
      replacement.disabled = false;
    }
  });
};

const updateBookingComposerSummaryWithoutQuantities = updateBookingComposerSummary;
updateBookingComposerSummary = function quantityBookingComposerSummary() {
  updateBookingComposerSummaryWithoutQuantities();
  const form = document.querySelector("#booking-create-form");
  const summary = document.querySelector("#booking-create-summary");
  if (!form || !summary) return;
  const { addons, quantities } = bookingSelectedServices(form);
  const labels = addons.map((addon) => bookingAddonLabel(addon, quantities[addon.public_name] || 1));
  const spans = summary.querySelectorAll("span");
  if (spans[0]) spans[0].textContent = labels.length ? labels.join(", ") : "без дополнений";
};

const updateBookingEditSummaryWithoutQuantities = updateBookingEditSummary;
updateBookingEditSummary = function quantityBookingEditSummary() {
  updateBookingEditSummaryWithoutQuantities();
  const form = document.querySelector("#booking-edit-form");
  const summary = document.querySelector("#booking-edit-summary");
  if (!form || !summary) return;
  const { addons, quantities } = selectedEditServices(form);
  const labels = addons.map((addon) => bookingAddonLabel(addon, quantities[addon.public_name] || 1));
  const spans = summary.querySelectorAll("span");
  if (spans[0]) {
    const base = form.elements.service_name.value || "Выберите процедуру";
    spans[0].textContent = `${base} · ${labels.length ? labels.join(", ") : "без дополнений"}`;
  }
};
