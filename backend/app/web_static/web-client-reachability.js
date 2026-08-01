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
    not_connected: "Нет в Telegram",
  };
  return labels[stateValue] || labels.not_connected;
}

function renderReachabilityBadge(card, stateValue) {
  const badge = document.createElement("span");
  badge.className = `client-reachability-badge reachability-${stateValue}`;
  badge.textContent = reachabilityLabel(stateValue);
  card.querySelector("h3")?.insertAdjacentElement("afterend", badge);
}

function clientLinkErrorText(error) {
  const messages = {
    client_not_found: "Карточка больше недоступна.",
    client_already_linked: "Эта карточка уже связана с другой клиенткой Telegram.",
    client_bot_username_not_configured: "Ссылка для записи пока не настроена.",
  };
  return messages[error.message] || "Не удалось подготовить приглашение.";
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
  const copy = inviteCopy(url);
  block.innerHTML = `
    <p>${personal ? "Персональная ссылка для этой клиентки" : "Приглашение для записи в Telegram"}</p>
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

async function createPersonalInvite(clientId, button) {
  const card = button.closest(".client-card");
  const actions = button.closest(".client-reachability-actions");
  button.disabled = true;
  actions?.querySelector(".client-invite-error")?.remove();
  try {
    const payload = await api(`/web/api/client-linking/clients/${encodeURIComponent(clientId)}/personal-link`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (card && payload.invitation_url) {
      renderInviteBlock(card, { url: payload.invitation_url, personal: true });
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
  document.querySelectorAll(".client-card[data-client-id]").forEach((card) => {
    const clientId = card.dataset.clientId;
    const stateValue = clientReachabilityState.byClient.get(clientId) || "not_connected";
    renderReachabilityBadge(card, stateValue);
    const actions = document.createElement("div");
    actions.className = "client-reachability-actions";
    if (stateValue === "not_connected" || stateValue === "unreachable") {
      actions.innerHTML = `<button class="secondary-button" type="button" data-personal-invite="${escapeHtml(clientId)}">Пригласить</button>`;
      card.append(actions);
    }
  });
  bindPersonalInviteButtons();
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
    <button id="show-client-invitation" class="secondary-button" type="button" ${reachability.invitation_url ? "" : "disabled"}>Пригласить клиенток</button>`;
  actions.prepend(wrapper);

  document.querySelector("#connected-clients-only")?.addEventListener("change", (event) => {
    clientReachabilityState.connectedOnly = event.target.checked;
    renderClients();
  });
  document.querySelector("#show-client-invitation")?.addEventListener("click", () => {
    const page = document.querySelector("#page-content");
    if (page && reachability.invitation_url) {
      renderInviteBlock(page, { url: reachability.invitation_url });
      page.querySelector(".client-invite-block")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
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
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    const page = document.querySelector("#page-content");
    if (page) page.innerHTML = '<div class="panel error-state">Не удалось загрузить клиенток.</div>';
  }
};
