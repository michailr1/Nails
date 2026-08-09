const clientRequestsState = { requests: [] };

function requestDateTime(value) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: state.timezone,
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function requestIsoDate(value) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: state.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

function requestAddonLabel(request) {
  const names = request.addon_names || [];
  if (!names.length) return "Без дополнений";
  return names.map((name) => {
    const quantity = request.addon_quantities?.[name.toLocaleLowerCase("ru-RU")]
      ?? request.addon_quantities?.[name]
      ?? null;
    return quantity && quantity > 1 ? `${name} ×${quantity}` : name;
  }).join(", ");
}

function requestCountLabel(count) {
  if (count === 1) return "1 просит записаться";
  return `${count} просят записаться`;
}

function requestNoteBlock(request) {
  if (!request.note) return "";
  return `<div class="info-note"><strong>Заметка клиентки</strong><br>${escapeHtml(request.note)}</div>`;
}

function requestCard(request) {
  return `<article class="panel client-request-card" data-request-id="${escapeHtml(request.id)}">
    <div class="client-request-head">
      <div><span class="client-request-kicker">Просит записаться</span><h2>${escapeHtml(request.requested_public_name || "Клиентка")}</h2></div>
      <time>${escapeHtml(requestDateTime(request.starts_at))}</time>
    </div>
    <div class="client-request-composition">
      <strong>${escapeHtml(request.service_name)}</strong>
      <span>${escapeHtml(requestAddonLabel(request))}</span>
    </div>
    ${requestNoteBlock(request)}
    <p class="client-request-note">Это просьба о времени, а не запись. Вы можете изменить состав и время перед подтверждением.</p>
    <div class="client-request-actions">
      <button class="primary-button" type="button" data-request-approve="${escapeHtml(request.id)}">Проверить и подтвердить</button>
      <button class="secondary-button" type="button" data-request-reject="${escapeHtml(request.id)}">Не получится</button>
    </div>
  </article>`;
}

function clientRequestErrorText(error) {
  const messages = {
    booking_overlap: "Это время уже занято другой записью. Заявка не изменилась — выберите другое время.",
    booking_on_day_off: "На это время сейчас нельзя создать запись.",
    service_not_found: "Процедуры больше нет в активном прайсе.",
    addon_not_found: "Одно из дополнений больше недоступно.",
    client_not_found: "Выбранная карточка клиентки больше недоступна.",
    client_already_linked: "Эта карточка уже связана с другой клиенткой Telegram.",
    client_name_conflict: "Клиентка с таким именем уже есть. Выберите существующую карточку явно.",
    booking_request_not_pending: "Эта просьба уже обработана.",
  };
  return messages[error.message] || "Не удалось обработать просьбу. Проверьте данные и попробуйте ещё раз.";
}

function closeClientRequestDialog() {
  document.querySelector("#client-request-dialog")?.remove();
}

function requestServicePrice(service) {
  if (!service) return "";
  if (typeof bookingServicePrice === "function") return bookingServicePrice(service);
  const amount = service.price_amount;
  return amount == null ? "" : `${Number(amount).toLocaleString("ru-RU")} ₽`;
}

function requestAddonChoices(services, request) {
  const selected = new Set(request.addon_names || []);
  const quantities = request.addon_quantities || {};
  if (!services.length) return '<p class="muted small">Дополнений в прайсе пока нет.</p>';
  return services.map((service) => {
    const checked = selected.has(service.public_name);
    const quantity = quantities[service.public_name.toLocaleLowerCase("ru-RU")]
      ?? quantities[service.public_name]
      ?? 1;
    return `<label class="booking-addon">
      <input type="checkbox" name="addon_names" value="${escapeHtml(service.public_name)}" ${checked ? "checked" : ""}>
      <span><strong>${escapeHtml(service.public_name)}</strong><small>${escapeHtml(requestServicePrice(service))}${service.extra_minutes ? ` · +${escapeHtml(service.extra_minutes)} мин` : ""}</small></span>
      ${service.quantity_supported ? `<input class="client-request-addon-quantity" type="number" min="1" max="100" step="1" data-addon-quantity="${escapeHtml(service.public_name)}" value="${escapeHtml(quantity)}" ${checked ? "" : "disabled"} aria-label="Количество ${escapeHtml(service.public_name)}">` : ""}
    </label>`;
  }).join("");
}

function requestSlotLabel(value) {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: state.timezone,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

async function refreshRequestSlots(dialog, request) {
  const form = dialog.querySelector("form");
  const select = form.elements.starts_at;
  const status = dialog.querySelector("#client-request-slot-status");
  const day = form.elements.day.value;
  const serviceName = form.elements.service_name.value;
  if (!day || !serviceName) return;
  select.disabled = true;
  status.textContent = "Проверяю свободное время…";
  try {
    const query = new URLSearchParams({ day, service_name: serviceName });
    const payload = await api(`/web/api/client-requests/slots?${query}`);
    const slots = payload.starts_at || [];
    const requestedInstant = new Date(request.starts_at).getTime();
    select.innerHTML = slots.length
      ? slots.map((slot) => `<option value="${escapeHtml(slot)}" ${new Date(slot).getTime() === requestedInstant ? "selected" : ""}>${escapeHtml(requestSlotLabel(slot))}</option>`).join("")
      : '<option value="">Свободного времени нет</option>';
    if (slots.length && !slots.some((slot) => new Date(slot).getTime() === requestedInstant)) {
      select.insertAdjacentHTML("afterbegin", '<option value="" selected>Выберите другое время</option>');
      status.textContent = "Запрошенное время уже недоступно. Выберите другое.";
    } else {
      status.textContent = slots.length ? "Показываем свободное время мастера." : "На эту дату свободного времени нет.";
    }
    select.disabled = !slots.length;
  } catch (error) {
    select.innerHTML = '<option value="">Не удалось загрузить время</option>';
    status.textContent = clientRequestErrorText(error);
  }
}

function requestApprovalPayload(form) {
  const addonNames = [...form.querySelectorAll('input[name="addon_names"]:checked')].map((input) => input.value);
  const addonQuantities = {};
  addonNames.forEach((name) => {
    const input = [...form.querySelectorAll("[data-addon-quantity]")].find((item) => item.dataset.addonQuantity === name);
    if (input) addonQuantities[name.toLocaleLowerCase("ru-RU")] = Number(input.value || 1);
  });
  const price = form.elements.price_override_amount.value;
  const duration = form.elements.duration_override_minutes.value;
  const resolution = form.elements.resolution.value;
  return {
    resolution,
    client_id: resolution === "link_existing" ? form.elements.client_id.value : null,
    service_name: form.elements.service_name.value,
    addon_names: addonNames,
    addon_quantities: addonQuantities,
    starts_at: form.elements.starts_at.value,
    price_override_amount: price === "" ? null : Number(price),
    duration_override_minutes: duration === "" ? null : Number(duration),
  };
}

function updateRequestDialogSummary(dialog) {
  const form = dialog.querySelector("form");
  const target = dialog.querySelector("#client-request-final-summary");
  if (!target) return;
  const addons = [...form.querySelectorAll('input[name="addon_names"]:checked')].map((input) => input.value);
  const time = form.elements.starts_at.value ? requestDateTime(form.elements.starts_at.value) : "выберите время";
  target.innerHTML = `<strong>Итоговая запись</strong><span>${escapeHtml(form.elements.service_name.value || "Процедура")} · ${escapeHtml(addons.length ? addons.join(", ") : "без дополнений")}</span><span>${escapeHtml(time)}</span>`;
}

function renderClientRequestDialog(request, clients, services, preselect = null) {
  const activeClients = clients.filter((client) => client.profile_status === "active");
  const activeServices = services.filter((service) => service.is_active);
  const bases = activeServices.filter((service) => service.kind === "base");
  const addons = activeServices.filter((service) => service.kind === "addon");
  const preselectedClientId = preselect?.client_id || "";
  const hasPreselect = activeClients.some((client) => client.client_id === preselectedClientId);
  const dialog = document.createElement("dialog");
  dialog.id = "client-request-dialog";
  dialog.className = "client-request-dialog booking-edit-dialog";
  dialog.innerHTML = `<form method="dialog" class="client-request-dialog-card booking-form">
    <div class="client-request-dialog-head">
      <div><p class="eyebrow">Просит записаться</p><h2>${escapeHtml(request.requested_public_name || "Клиентка")}</h2></div>
      <button class="ghost-button" value="close" type="submit" aria-label="Закрыть">×</button>
    </div>
    <div class="client-request-summary"><span>Клиентка попросила:</span><strong>${escapeHtml(request.service_name)}</strong><span>${escapeHtml(requestAddonLabel(request))}</span><span>${escapeHtml(requestDateTime(request.starts_at))}</span></div>
    ${requestNoteBlock(request)}
    <label class="catalog-field"><span>Основная процедура</span><select name="service_name" required>${bases.map((service) => `<option value="${escapeHtml(service.public_name)}" ${service.public_name === request.service_name ? "selected" : ""}>${escapeHtml(service.public_name)}</option>`).join("")}</select></label>
    <div class="booking-addons"><span class="booking-field-title">Дополнения <em>необязательно</em></span>${requestAddonChoices(addons, request)}</div>
    <div class="booking-edit-date-time"><label class="booking-edit-field">Дата<input name="day" type="date" value="${escapeHtml(requestIsoDate(request.starts_at))}" required></label><label class="booking-edit-field">Свободное время<select name="starts_at" required></select></label></div>
    <p id="client-request-slot-status" class="muted small" role="status"></p>
    <details class="booking-overrides"><summary>Уточнить итоговую цену или длительность</summary><div class="booking-override-grid"><label class="catalog-field"><span>Цена, ₽</span><input name="price_override_amount" type="number" min="0" step="1" placeholder="Автоматически из прайса"></label><label class="catalog-field"><span>Время, мин</span><input name="duration_override_minutes" type="number" min="1" max="1440" step="1" placeholder="Автоматически из прайса"></label></div></details>
    <div id="client-request-final-summary" class="booking-create-summary" aria-live="polite"></div>
    ${hasPreselect ? `<div class="info-note"><strong>Похоже, клиентка уже была у вас.</strong><br>${escapeHtml(preselect.reason || "Совпала карточка по указанному номеру.")} Проверьте карточку перед подтверждением.</div>` : ""}
    <fieldset class="client-resolution">
      <legend>Кто это?</legend>
      <label><input type="radio" name="resolution" value="create_new" ${hasPreselect ? "" : "checked"}><span><strong>Новая клиентка</strong><small>Создать новую карточку «${escapeHtml(request.requested_public_name || "Клиентка") }»</small></span></label>
      <label><input type="radio" name="resolution" value="link_existing" ${hasPreselect ? "checked" : ""}><span><strong>Уже была у меня</strong><small>Связать просьбу с существующей карточкой</small></span></label>
    </fieldset>
    <label id="existing-client-field" class="catalog-field client-request-client-select" ${hasPreselect ? "" : "hidden"}><span>Выберите клиентку</span><select name="client_id"><option value="">Выберите карточку</option>${activeClients.map((client) => `<option value="${escapeHtml(client.client_id)}" ${client.client_id === preselectedClientId ? "selected" : ""}>${escapeHtml(client.public_name)}</option>`).join("")}</select></label>
    <p class="muted small">Карточки не связываются автоматически по имени или номеру, введённому вручную. Совпавший номер — только подсказка вам.</p>
    <p id="client-request-error" class="booking-edit-error" role="alert"></p>
    <div class="client-request-dialog-actions"><button id="client-request-confirm" class="primary-button" type="button">Подтвердить итоговую запись</button><button class="secondary-button" value="close" type="submit">Назад</button></div>
  </form>`;
  document.body.append(dialog);
  dialog.addEventListener("close", closeClientRequestDialog);
  const form = dialog.querySelector("form");
  dialog.querySelectorAll('input[name="resolution"]').forEach((input) => input.addEventListener("change", () => {
    dialog.querySelector("#existing-client-field").hidden = input.value !== "link_existing" || !input.checked;
  }));
  dialog.querySelectorAll('input[name="addon_names"]').forEach((input) => input.addEventListener("change", () => {
    const quantity = [...dialog.querySelectorAll("[data-addon-quantity]")].find((item) => item.dataset.addonQuantity === input.value);
    if (quantity) quantity.disabled = !input.checked;
    updateRequestDialogSummary(dialog);
  }));
  form.elements.day.addEventListener("change", async () => { await refreshRequestSlots(dialog, request); updateRequestDialogSummary(dialog); });
  form.elements.service_name.addEventListener("change", async () => { await refreshRequestSlots(dialog, request); updateRequestDialogSummary(dialog); });
  form.addEventListener("input", () => updateRequestDialogSummary(dialog));
  form.addEventListener("change", () => updateRequestDialogSummary(dialog));
  dialog.querySelector("#client-request-confirm").addEventListener("click", async () => {
    const payload = requestApprovalPayload(form);
    const errorLine = dialog.querySelector("#client-request-error");
    if (payload.resolution === "link_existing" && !payload.client_id) {
      errorLine.textContent = "Выберите существующую карточку клиентки.";
      return;
    }
    if (!payload.starts_at) {
      errorLine.textContent = "Выберите свободное время.";
      return;
    }
    const summary = dialog.querySelector("#client-request-final-summary").innerText;
    if (!window.confirm(`Создать эту запись?\n\n${summary}`)) return;
    const button = dialog.querySelector("#client-request-confirm");
    button.disabled = true;
    errorLine.textContent = "";
    try {
      await api(`/web/api/client-requests/${encodeURIComponent(request.id)}/approve`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      closeClientRequestDialog();
      if (state.view === "clients") await renderClients();
      else await renderCalendar();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = clientRequestErrorText(error);
      button.disabled = false;
      await refreshRequestSlots(dialog, request);
    }
  });
  dialog.showModal();
  refreshRequestSlots(dialog, request).then(() => updateRequestDialogSummary(dialog));
}

function showClientRequestSurfaceError(message) {
  const host = document.querySelector("#client-request-surface-status");
  if (!host) return;
  host.textContent = message;
}

async function openClientRequestDialog(request) {
  try {
    const [clientsPayload, servicesPayload, preselect] = await Promise.all([
      api("/web/api/clients"),
      api("/web/api/services"),
      api(`/web/api/client-linking/requests/${encodeURIComponent(request.id)}/preselect`).catch(() => null),
    ]);
    renderClientRequestDialog(request, clientsPayload.clients || [], servicesPayload.services || [], preselect);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    showClientRequestSurfaceError("Не удалось открыть просьбу о записи.");
  }
}

function bindClientRequestActions(requests) {
  document.querySelectorAll("[data-request-approve]").forEach((button) => {
    button.addEventListener("click", () => {
      const request = requests.find((item) => item.id === button.dataset.requestApprove);
      if (request) openClientRequestDialog(request);
    });
  });
  document.querySelectorAll("[data-open-request]").forEach((button) => {
    button.addEventListener("click", () => {
      const request = requests.find((item) => item.id === button.dataset.openRequest);
      if (request) openClientRequestDialog(request);
    });
  });
  document.querySelectorAll("[data-request-reject]").forEach((button) => {
    button.addEventListener("click", async () => {
      const request = requests.find((item) => item.id === button.dataset.requestReject);
      if (!request || !window.confirm(`Не подтверждать просьбу ${request.requested_public_name || "клиентки"}?`)) return;
      button.disabled = true;
      try {
        await api(`/web/api/client-requests/${encodeURIComponent(request.id)}/reject`, { method: "POST", body: JSON.stringify({}) });
        if (state.view === "clients") await renderClients();
        else await renderCalendar();
      } catch (error) {
        if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
        showClientRequestSurfaceError(clientRequestErrorText(error));
        button.disabled = false;
      }
    });
  });
}

function requestsForDate(requests, iso) {
  return requests.filter((request) => requestIsoDate(request.starts_at) === iso);
}

function decorateCalendarRequestDays(requests) {
  if (!requests.length) return;
  if (state.calendarMode === "month") {
    document.querySelectorAll("[data-open-date]").forEach((cell) => {
      const count = requestsForDate(requests, cell.dataset.openDate).length;
      if (!count) return;
      const marker = document.createElement("span");
      marker.className = "client-request-day-marker";
      marker.textContent = requestCountLabel(count);
      cell.append(marker);
    });
    return;
  }
  if (state.calendarMode === "week") {
    const range = periodRange();
    document.querySelectorAll(".week-day").forEach((day, index) => {
      const iso = addDays(range.dateFrom, index);
      const count = requestsForDate(requests, iso).length;
      if (!count) return;
      const marker = document.createElement("span");
      marker.className = "client-request-day-marker";
      marker.textContent = requestCountLabel(count);
      day.querySelector(".panel-header")?.append(marker);
    });
    return;
  }
  const count = requestsForDate(requests, state.selectedDate).length;
  if (!count) return;
  const marker = document.createElement("span");
  marker.className = "client-request-day-marker";
  marker.textContent = requestCountLabel(count);
  document.querySelector("#page-content .panel-header")?.append(marker);
}

function renderCalendarRequestSummary(requests) {
  if (!requests.length) return;
  const toolbar = document.querySelector("#page-content .calendar-toolbar");
  if (!toolbar) return;
  const summary = document.createElement("section");
  summary.className = "client-request-summary-row";
  summary.innerHTML = `
    <button class="client-request-summary-button" type="button" aria-expanded="false">
      <span>${escapeHtml(requestCountLabel(requests.length))}</span><span>посмотреть</span>
    </button>
    <span id="client-request-surface-status" class="small" role="status"></span>
    <div class="client-request-inline-list" hidden>${requests.map(requestCard).join("")}</div>`;
  toolbar.insertAdjacentElement("afterend", summary);
  const button = summary.querySelector(".client-request-summary-button");
  const list = summary.querySelector(".client-request-inline-list");
  button.addEventListener("click", () => {
    list.hidden = !list.hidden;
    button.setAttribute("aria-expanded", String(!list.hidden));
  });
  bindClientRequestActions(requests);
}

function decorateClientCardsWithRequests(requests) {
  requests.filter((request) => request.client_id).forEach((request) => {
    const card = document.querySelector(`.client-card[data-client-id="${CSS.escape(request.client_id)}"]`);
    if (!card) return;
    const note = document.createElement("button");
    note.className = "client-card-request-note";
    note.type = "button";
    note.dataset.openRequest = request.id;
    note.textContent = `Просит записаться · ${requestDateTime(request.starts_at)}`;
    card.append(note);
  });
  bindClientRequestActions(requests);
}

async function loadPendingClientRequests() {
  const payload = await api("/web/api/client-requests");
  clientRequestsState.requests = payload.requests || [];
  return clientRequestsState.requests;
}

const originalRenderCalendarForClientRequests = renderCalendar;
renderCalendar = async function renderCalendarWithClientRequests() {
  await originalRenderCalendarForClientRequests();
  if (state.view !== "calendar" || !document.querySelector("#page-content")) return;
  try {
    const requests = await loadPendingClientRequests();
    renderCalendarRequestSummary(requests);
    decorateCalendarRequestDays(requests);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
  }
};

const originalRenderClientsForClientRequests = renderClients;
renderClients = async function renderClientsWithClientRequests() {
  await originalRenderClientsForClientRequests();
  if (state.view !== "clients" || !document.querySelector("#page-content")) return;
  try {
    const requests = await loadPendingClientRequests();
    decorateClientCardsWithRequests(requests);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
  }
};