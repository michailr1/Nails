const clientRequestsState = { pendingCount: null };

const originalAppShellForClientRequests = appShell;
appShell = function appShellWithClientRequests(title, body) {
  originalAppShellForClientRequests(title, body);
  const nav = document.querySelector(".nav");
  if (!nav || nav.querySelector('[data-view="client-requests"]')) return;
  const button = document.createElement("button");
  button.className = `tab-button ${state.view === "client-requests" ? "active" : ""}`;
  button.dataset.view = "client-requests";
  button.type = "button";
  button.innerHTML = `Заявки${clientRequestsState.pendingCount ? `<span class="request-count">${clientRequestsState.pendingCount}</span>` : ""}`;
  button.addEventListener("click", () => {
    state.view = "client-requests";
    renderApp();
  });
  nav.append(button);
};

const originalRenderAppForClientRequests = renderApp;
renderApp = async function renderAppWithClientRequests() {
  if (state.view === "client-requests") {
    clearPoll();
    try {
      await api("/web/api/auth/session");
    } catch (error) {
      if (error.status === 401) return renderLogin();
      return renderLogin("Не удалось проверить сессию.");
    }
    return renderClientRequests();
  }
  const result = await originalRenderAppForClientRequests();
  refreshClientRequestCount();
  return result;
};

function requestDateTime(value) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: APP_TIMEZONE,
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
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

function requestCard(request) {
  return `<article class="panel client-request-card" data-request-id="${escapeHtml(request.id)}">
    <div class="client-request-head">
      <div><span class="client-request-kicker">Новая заявка</span><h2>${escapeHtml(request.requested_public_name || "Клиентка")}</h2></div>
      <time>${escapeHtml(requestDateTime(request.starts_at))}</time>
    </div>
    <div class="client-request-composition">
      <strong>${escapeHtml(request.service_name)}</strong>
      <span>${escapeHtml(requestAddonLabel(request))}</span>
    </div>
    <p class="client-request-note">Время пока не забронировано. При подтверждении Нэйли ещё раз проверит расписание.</p>
    <div class="client-request-actions">
      <button class="primary-button" type="button" data-request-approve="${escapeHtml(request.id)}">Подтвердить</button>
      <button class="secondary-button" type="button" data-request-reject="${escapeHtml(request.id)}">Не получится</button>
    </div>
  </article>`;
}

async function refreshClientRequestCount() {
  try {
    const payload = await api("/web/api/client-requests");
    clientRequestsState.pendingCount = (payload.requests || []).length;
    const current = document.querySelector('[data-view="client-requests"]');
    if (!current) return;
    current.innerHTML = `Заявки${clientRequestsState.pendingCount ? `<span class="request-count">${clientRequestsState.pendingCount}</span>` : ""}`;
  } catch (error) {
    if (error.status === 401) return;
  }
}

function clientRequestErrorText(error) {
  const messages = {
    booking_overlap: "Это время уже занято другой записью. Заявка остаётся без изменений — выберите с клиенткой другое время.",
    booking_on_day_off: "На это время сейчас нельзя создать запись.",
    service_not_found: "Процедуры больше нет в активном прайсе.",
    addon_not_found: "Одно из дополнений больше недоступно.",
    client_not_found: "Выбранная карточка клиентки больше недоступна.",
    client_already_linked: "Эта карточка уже связана с другой клиенткой Telegram.",
    client_name_conflict: "Клиентка с таким именем уже есть. Выберите существующую карточку явно.",
    booking_request_not_pending: "Эта заявка уже обработана.",
  };
  return messages[error.message] || "Не удалось обработать заявку. Обновите список и попробуйте ещё раз.";
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
      <div><p class="eyebrow">Заявка на запись</p><h2>${escapeHtml(request.requested_public_name || "Клиентка")}</h2></div>
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
      <label><input type="radio" name="resolution" value="link_existing" ${hasPreselect ? "checked" : ""}><span><strong>Уже была у меня</strong><small>Связать заявку с существующей карточкой</small></span></label>
    </fieldset>
    <label id="existing-client-field" class="catalog-field client-request-client-select" ${hasPreselect ? "" : "hidden"}><span>Выберите клиентку</span><select name="client_id"><option value="">Выберите карточку</option>${activeClients.map((client) => `<option value="${escapeHtml(client.client_id)}" ${client.client_id === preselectedClientId ? "selected" : ""}>${escapeHtml(client.public_name)}</option>`).join("")}</select></label>
    <p class="muted small">Нэйли никогда не связывает карточки автоматически по имени или по номеру, введённому вручную. Совпавший номер — только подсказка вам.</p>
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
      await renderClientRequests();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = clientRequestErrorText(error);
      button.disabled = false;
    }
  });
  dialog.showModal();
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
    window.alert("Не удалось загрузить карточки клиенток.");
  }
}

function bindClientRequestActions(requests) {
  document.querySelectorAll("[data-request-approve]").forEach((button) => {
    button.addEventListener("click", () => {
      const request = requests.find((item) => item.id === button.dataset.requestApprove);
      if (request) openClientRequestDialog(request);
    });
  });
  document.querySelectorAll("[data-request-reject]").forEach((button) => {
    button.addEventListener("click", async () => {
      const request = requests.find((item) => item.id === button.dataset.requestReject);
      if (!request || !window.confirm(`Не подтверждать заявку ${request.requested_public_name || "клиентки"}?`)) return;
      button.disabled = true;
      try {
        await api(`/web/api/client-requests/${encodeURIComponent(request.id)}/reject`, { method: "POST", body: JSON.stringify({}) });
        await renderClientRequests();
      } catch (error) {
        if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
        window.alert(clientRequestErrorText(error));
        button.disabled = false;
      }
    });
  });
}

async function renderClientRequests() {
  appShell("Заявки", '<div class="loading-state">Загружаем новые заявки…</div>');
  try {
    const payload = await api("/web/api/client-requests");
    const requests = payload.requests || [];
    clientRequestsState.pendingCount = requests.length;
    const page = document.querySelector("#page-content");
    page.innerHTML = requests.length
      ? `<div class="client-request-list">${requests.map(requestCard).join("")}</div>`
      : '<div class="empty-state"><h2>Новых заявок нет</h2><p class="muted">Когда клиентка отправит заявку на запись, она появится здесь.</p></div>';
    bindClientRequestActions(requests);
  } catch (error) {
    if (error.status === 401) return renderLogin();
    document.querySelector("#page-content").innerHTML = '<div class="empty-state"><h2>Не удалось загрузить заявки</h2><p class="muted">Попробуйте обновить страницу.</p></div>';
  }
}