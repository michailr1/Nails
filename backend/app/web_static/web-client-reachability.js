const clientReachabilityState = {
  connectedOnly: false,
  byClient: new Map(),
};

const originalClientCardForReachability = clientCard;
clientCard = function clientCardWithReachability(client) {
  const html = originalClientCardForReachability(client);
  return html.replace(
    '<article class="client-card">',
    `<article class="client-card" data-client-id="${escapeHtml(client.client_id)}">`,
  );
};

function reachabilityLabel(stateValue) {
  const labels = {
    reachable: "На связи в Telegram",
    unknown: "На связи в Telegram",
    unreachable: "Сообщения не доходят",
    not_connected: "Не подключена",
  };
  return labels[stateValue] || labels.not_connected;
}

function renderReachabilityBadge(card, stateValue) {
  card.querySelector(".client-reachability-badge")?.remove();
  const name = card.querySelector(".client-card-summary-main strong, h3");
  if (!name) return;
  let row = name.closest(".client-name-status");
  if (!row) {
    row = document.createElement("span");
    row.className = "client-name-status";
    name.replaceWith(row);
    row.append(name);
  }
  const badge = document.createElement("span");
  badge.className = `client-reachability-badge reachability-${stateValue}`;
  badge.textContent = reachabilityLabel(stateValue);
  row.append(badge);
}

function clientLinkErrorText(error) {
  const messages = {
    client_not_found: "Карточка больше недоступна.",
    client_already_linked: "Эта карточка уже связана с другой клиенткой Telegram.",
    client_bot_username_not_configured: "Ссылка для записи пока не настроена.",
    master_public_profile_required: "Сначала заполните, как вас увидят клиентки.",
  };
  return messages[error.message] || "Не удалось подготовить ссылку.";
}

async function copyText(value, statusNode) {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  if (statusNode) {
    statusNode.textContent = "Скопировано";
    window.setTimeout(() => {
      if (statusNode.isConnected) statusNode.textContent = "";
    }, 1800);
  }
}

function inviteCopy(url) {
  return `Записаться ко мне можно в Telegram — там есть прайс и свободное время.\n\n${url}`;
}

function renderInviteBlock(container, { url, personal = false }) {
  container.querySelector(".client-invite-block")?.remove();
  const block = document.createElement("div");
  block.className = "client-invite-block";
  const copy = personal ? url : inviteCopy(url);
  block.innerHTML = `
    <p>${personal ? "Ссылка для этой клиентки" : "Общая ссылка для записи"}</p>
    ${personal ? "" : '<small class="muted">Подходит для любой новой клиентки. Персональная ссылка находится в карточке конкретной клиентки.</small>'}
    <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>
    <div class="client-invite-actions">
      <button class="secondary-button" type="button" data-copy-invite>Скопировать</button>
      <span class="muted small" data-copy-status aria-live="polite"></span>
    </div>`;
  block.querySelector("[data-copy-invite]")?.addEventListener("click", () => {
    copyText(copy, block.querySelector("[data-copy-status]"));
  });
  container.append(block);
}

function renderPublicProfileSetup(reachability) {
  const page = document.querySelector("#page-content");
  const profile = reachability.public_profile || {};
  if (!page || profile.ready) return;
  const panel = document.createElement("section");
  panel.className = "panel client-public-profile-panel";
  panel.innerHTML = `
    <p class="eyebrow">Перед приглашением</p>
    <h2>Как вас увидят клиентки</h2>
    <p>Укажите имя мастера. Контакт необязателен — его клиентка увидит, если понадобится связаться напрямую.</p>
    <form id="client-public-profile-form" class="client-public-profile-form">
      <label><span>Имя мастера</span><input name="display_name" maxlength="160" required placeholder="Например, Настя"></label>
      <label><span>Контакт <small>необязательно</small></span><input name="public_contact" maxlength="160" placeholder="Телефон или @username"></label>
      <p class="booking-edit-error" role="alert"></p>
      <button class="primary-button" type="submit">Сохранить и продолжить</button>
    </form>`;
  page.prepend(panel);
  panel.querySelector("form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button");
    const errorLine = form.querySelector(".booking-edit-error");
    button.disabled = true;
    errorLine.textContent = "";
    try {
      await api("/web/api/client-linking/public-profile", {
        method: "PUT",
        body: JSON.stringify({
          display_name: form.elements.display_name.value,
          public_contact: form.elements.public_contact.value || null,
        }),
      });
      await renderClients();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = "Не удалось сохранить. Проверьте имя и попробуйте ещё раз.";
      button.disabled = false;
    }
  });
}

async function createPersonalInvite(clientId, button) {
  const card = button.closest(".client-card");
  const actions = button.closest(".client-reachability-actions");
  const status = actions?.querySelector("[data-personal-copy-status]");
  button.disabled = true;
  actions?.querySelector(".client-invite-error")?.remove();
  try {
    const payload = await api(`/web/api/client-linking/clients/${encodeURIComponent(clientId)}/personal-link`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (card && payload.invitation_url) {
      renderInviteBlock(card, { url: payload.invitation_url, personal: true });
      await copyText(payload.invitation_url, status);
    }
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    if (actions) {
      const line = document.createElement("span");
      line.className = "client-invite-error small";
      line.textContent = clientLinkErrorText(error);
      actions.append(line);
    }
  } finally {
    button.disabled = false;
  }
}

function bindPersonalInviteButtons() {
  document.querySelectorAll("[data-personal-invite]").forEach((button) => {
    button.addEventListener("click", () => createPersonalInvite(button.dataset.personalInvite, button));
  });
}

function decorateClientCards(reachability) {
  clientReachabilityState.byClient = new Map(
    (reachability.items || []).map((item) => [item.client_id, item.state]),
  );
  document.querySelectorAll(".client-card").forEach((card) => {
    const opener = card.querySelector("[data-client-open]");
    const clientId = card.dataset.clientId || opener?.dataset.clientOpen;
    if (!clientId) return;
    card.dataset.clientId = clientId;
    const stateValue = clientReachabilityState.byClient.get(clientId) || "not_connected";
    renderReachabilityBadge(card, stateValue);
    card.querySelector(".client-reachability-actions")?.remove();
    const actions = document.createElement("div");
    actions.className = "client-reachability-actions";
    const disabled = reachability.public_profile?.ready ? "" : "disabled";
    actions.innerHTML = `
      <span class="client-personal-link-title">Ссылка для этой клиентки</span>
      <span class="client-personal-link-help">Откроется только для этой карточки. Кнопка сразу скопирует готовую ссылку.</span>
      <button class="secondary-button" type="button" data-personal-invite="${escapeHtml(clientId)}" ${disabled}>Скопировать ссылку</button>
      <span class="muted small" data-personal-copy-status aria-live="polite"></span>`;
    card.append(actions);
  });
  bindPersonalInviteButtons();
}

function renderReachabilitySummary(reachability) {
  const page = document.querySelector("#page-content");
  if (!page) return;
  page.querySelector(".client-reachability-summary")?.remove();
  const items = reachability.items || [];
  const connected = items.filter((item) => ["reachable", "unknown"].includes(item.state)).length;
  const summary = document.createElement("div");
  summary.className = "info-note client-reachability-summary";
  summary.innerHTML = `<strong>${connected} из ${items.length} на связи</strong><span>Статус каждой клиентки показан рядом с именем.</span>`;
  page.prepend(summary);
}

async function showGeneralInvitation(button) {
  const page = document.querySelector("#page-content");
  if (!page) return;
  button.disabled = true;
  try {
    const payload = await api("/web/api/client-linking/general-link", {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (payload.invitation_url) {
      renderInviteBlock(page, { url: payload.invitation_url });
      page.querySelector(".client-invite-block")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    const line = document.createElement("div");
    line.className = "panel error-state";
    line.textContent = clientLinkErrorText(error);
    page.prepend(line);
  } finally {
    button.disabled = false;
  }
}

function renderReachabilityControls(reachability) {
  const actions = document.querySelector("#page-actions");
  if (!actions) return;
  const wrapper = document.createElement("div");
  wrapper.className = "client-reachability-controls";
  wrapper.innerHTML = `
    <label class="client-connected-filter">
      <input id="connected-clients-only" type="checkbox" ${clientReachabilityState.connectedOnly ? "checked" : ""}>
      <span>Кому можно написать</span>
    </label>
    <button id="show-client-invitation" class="secondary-button" type="button" ${reachability.invitation_available ? "" : "disabled"}>Общая ссылка для записи</button>`;
  actions.prepend(wrapper);

  document.querySelector("#connected-clients-only")?.addEventListener("change", (event) => {
    clientReachabilityState.connectedOnly = event.target.checked;
    renderClients();
  });
  document.querySelector("#show-client-invitation")?.addEventListener("click", (event) => {
    showGeneralInvitation(event.currentTarget);
  });
}

async function renderFilteredClientsFromBackend() {
  appShell("Клиентки", '<div class="loading-state">Загружаем карточки…</div>');
  const actions = document.querySelector("#page-actions");
  actions.innerHTML = '<button id="export-clients" class="secondary-button" type="button">Выгрузить всех клиенток</button>';
  document.querySelector("#export-clients")?.addEventListener("click", () => {
    downloadExport("/web/api/exports/clients?format=xlsx", `clients-all-${todayInTimezone(APP_TIMEZONE)}.xlsx`);
  });
  const data = await api("/web/api/clients?connected_only=true");
  document.querySelector("#page-content").innerHTML = data.clients.length
    ? `<div class="client-grid">${data.clients.map(clientCard).join("")}</div>`
    : '<div class="panel empty">Сейчас нет клиенток, которым можно написать в Telegram.</div>';
}

const originalRenderClientsForReachability = renderClients;
renderClients = async function renderClientsWithReachability() {
  try {
    if (clientReachabilityState.connectedOnly) await renderFilteredClientsFromBackend();
    else await originalRenderClientsForReachability();
    if (state.view !== "clients" || !document.querySelector("#page-content")) return;
    const query = clientReachabilityState.connectedOnly ? "?connected_only=true" : "";
    const reachability = await api(`/web/api/client-linking/reachability${query}`);
    decorateClientCards(reachability);
    renderReachabilityControls(reachability);
    renderReachabilitySummary(reachability);
    renderPublicProfileSetup(reachability);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    const page = document.querySelector("#page-content");
    if (page) page.innerHTML = '<div class="panel error-state">Не удалось загрузить клиенток.</div>';
  }
};
