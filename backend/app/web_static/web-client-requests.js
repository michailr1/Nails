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
    <p class="client-request-note">Это просьба о времени, а не запись. При подтверждении расписание проверится ещё раз.</p>
    <div class="client-request-actions">
      <button class="primary-button" type="button" data-request-approve="${escapeHtml(request.id)}">Подтвердить</button>
      <button class="secondary-button" type="button" data-request-reject="${escapeHtml(request.id)}">Не получится</button>
    </div>
  </article>`;
}

function clientRequestErrorText(error) {
  const messages = {
    booking_overlap: "Это время уже занято другой записью. Просьба остаётся без изменений — выберите с клиенткой другое время.",
    booking_on_day_off: "На это время сейчас нельзя создать запись.",
    service_not_found: "Процедуры больше нет в активном прайсе.",
    addon_not_found: "Одно из дополнений больше недоступно.",
    client_not_found: "Выбранная карточка клиентки больше недоступна.",
    client_already_linked: "Эта карточка уже связана с другой клиенткой Telegram.",
    client_name_conflict: "Клиентка с таким именем уже есть. Выберите существующую карточку явно.",
    booking_request_not_pending: "Эта просьба уже обработана.",
  };
  return messages[error.message] || "Не удалось обработать просьбу. Обновите календарь и попробуйте ещё раз.";
}

function closeClientRequestDialog() {
  document.querySelector("#client-request-dialog")?.remove();
}

function renderClientRequestDialog(request, clients, preselect = null) {
  const activeClients = clients.filter((client) => client.profile_status === "active");
  const preselectedClientId = preselect?.client_id || "";
  const hasPreselect = activeClients.some((client) => client.client_id === preselectedClientId);
  const dialog = document.createElement("dialog");
  dialog.id = "client-request-dialog";
  dialog.className = "client-request-dialog";
  dialog.innerHTML = `<form method="dialog" class="client-request-dialog-card">
    <div class="client-request-dialog-head">
      <div><p class="eyebrow">Просит записаться</p><h2>${escapeHtml(request.requested_public_name || "Клиентка")}</h2></div>
      <button class="ghost-button" value="close" type="submit" aria-label="Закрыть">×</button>
    </div>
    <div class="client-request-summary">
      <strong>${escapeHtml(request.service_name)}</strong>
      <span>${escapeHtml(requestAddonLabel(request))}</span>
      <span>${escapeHtml(requestDateTime(request.starts_at))}</span>
    </div>
    ${hasPreselect ? `<div class="info-note"><strong>Похоже, клиентка уже была у вас.</strong><br>${escapeHtml(preselect.reason || "Совпала карточка по указанному номеру.")} Проверьте карточку перед подтверждением.</div>` : ""}
    <fieldset class="client-resolution">
      <legend>Кто это?</legend>
      <label><input type="radio" name="resolution" value="create_new" ${hasPreselect ? "" : "checked"}><span><strong>Новая клиентка</strong><small>Создать новую карточку «${escapeHtml(request.requested_public_name || "Клиентка") }»</small></span></label>
      <label><input type="radio" name="resolution" value="link_existing" ${hasPreselect ? "checked" : ""}><span><strong>Уже была у меня</strong><small>Связать просьбу с существующей карточкой</small></span></label>
    </fieldset>
    <label id="existing-client-field" class="catalog-field client-request-client-select" ${hasPreselect ? "" : "hidden"}><span>Выберите клиентку</span><select name="client_id"><option value="">Выберите карточку</option>${activeClients.map((client) => `<option value="${escapeHtml(client.client_id)}" ${client.client_id === preselectedClientId ? "selected" : ""}>${escapeHtml(client.public_name)}</option>`).join("")}</select></label>
    <p class="muted small">Карточки не связываются автоматически по имени или номеру, введённому вручную. Совпавший номер — только подсказка вам.</p>
    <p id="client-request-error" class="booking-edit-error" role="alert"></p>
    <div class="client-request-dialog-actions"><button id="client-request-confirm" class="primary-button" type="button">Подтвердить запись</button><button class="secondary-button" value="close" type="submit">Назад</button></div>
  </form>`;
  document.body.append(dialog);
  dialog.addEventListener("close", closeClientRequestDialog);
  dialog.querySelectorAll('input[name="resolution"]').forEach((input) => input.addEventListener("change", () => {
    dialog.querySelector("#existing-client-field").hidden = input.value !== "link_existing" || !input.checked;
  }));
  dialog.querySelector("#client-request-confirm").addEventListener("click", async () => {
    const form = dialog.querySelector("form");
    const resolution = form.elements.resolution.value;
    const clientId = form.elements.client_id.value;
    const errorLine = dialog.querySelector("#client-request-error");
    if (resolution === "link_existing" && !clientId) {
      errorLine.textContent = "Выберите существующую карточку клиентки.";
      return;
    }
    const button = dialog.querySelector("#client-request-confirm");
    button.disabled = true;
    errorLine.textContent = "";
    try {
      await api(`/web/api/client-requests/${encodeURIComponent(request.id)}/approve`, {
        method: "POST",
        body: JSON.stringify({ resolution, client_id: resolution === "link_existing" ? clientId : null }),
      });
      closeClientRequestDialog();
      if (state.view === "clients") await renderClients();
      else await renderCalendar();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = clientRequestErrorText(error);
      button.disabled = false;
    }
  });
  dialog.showModal();
}

function showClientRequestSurfaceError(message) {
  const host = document.querySelector("#client-request-surface-status");
  if (!host) return;
  host.textContent = message;
}

async function openClientRequestDialog(request) {
  try {
    const [payload, preselect] = await Promise.all([
      api("/web/api/clients"),
      api(`/web/api/client-linking/requests/${encodeURIComponent(request.id)}/preselect`).catch(() => null),
    ]);
    renderClientRequestDialog(request, payload.clients || [], preselect);
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
