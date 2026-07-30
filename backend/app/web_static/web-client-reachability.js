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
    reachable: "В боте",
    unknown: "В боте · ещё не проверено",
    unreachable: "Бот недоступен",
    not_connected: "Не подключена",
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
  };
  return messages[error.message] || "Не удалось выполнить действие.";
}

async function createPersonalInvite(clientId, button) {
  button.disabled = true;
  try {
    const payload = await api(`/web/api/client-linking/clients/${encodeURIComponent(clientId)}/personal-link`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const token = payload.token;
    const text = `Персональный код приглашения: ${token}\n\nОн одноразовый и действует ограниченное время. После запуска клиентского бота Нэйли соберёт из него готовую Telegram-ссылку.`;
    window.prompt("Приглашение для этой клиентки", text);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    window.alert(clientLinkErrorText(error));
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
    } else {
      actions.innerHTML = '<span class="muted small">Можно получать сообщения Нэйли</span>';
    }
    card.append(actions);
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
      <span>Только подключённые</span>
    </label>
    <button id="copy-client-invitation" class="secondary-button" type="button">Текст приглашения</button>
    <button id="sent-client-log" class="secondary-button" type="button">История сообщений</button>`;
  actions.prepend(wrapper);

  document.querySelector("#connected-clients-only")?.addEventListener("change", (event) => {
    clientReachabilityState.connectedOnly = event.target.checked;
    renderClients();
  });
  document.querySelector("#copy-client-invitation")?.addEventListener("click", async () => {
    const tokenSuffix = reachability.invitation_start_token
      ? `\n\nКод ссылки для записи: ${reachability.invitation_start_token}`
      : "";
    const invitation = `${reachability.invitation_text}${tokenSuffix}`;
    try {
      await navigator.clipboard.writeText(invitation);
      window.alert("Текст приглашения скопирован.");
    } catch {
      window.prompt("Скопируйте приглашение", invitation);
    }
  });
  document.querySelector("#sent-client-log")?.addEventListener("click", showSentClientLog);
}

async function showSentClientLog() {
  try {
    const rows = await api("/web/api/client-linking/sent");
    const lines = (rows || []).slice(0, 30).map((row) => {
      const when = new Date(row.created_at).toLocaleString("ru-RU");
      const names = { approved: "Запись подтверждена", rejected: "Заявка отклонена", cancelled: "Заявка отменена" };
      return `${when} — ${names[row.event_type] || row.event_type} — ${row.status}`;
    });
    window.alert(lines.length ? lines.join("\n") : "Отправленных сообщений пока нет.");
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    window.alert("Не удалось загрузить историю сообщений.");
  }
}

const originalRenderClientsForReachability = renderClients;
renderClients = async function renderClientsWithReachability() {
  await originalRenderClientsForReachability();
  if (state.view !== "clients" || !document.querySelector("#page-content")) return;
  try {
    const query = clientReachabilityState.connectedOnly ? "?connected_only=true" : "";
    const reachability = await api(`/web/api/client-linking/reachability${query}`);
    if (clientReachabilityState.connectedOnly) {
      const allowed = new Set((reachability.items || []).map((item) => item.client_id));
      document.querySelectorAll(".client-card[data-client-id]").forEach((card) => {
        if (!allowed.has(card.dataset.clientId)) card.remove();
      });
    }
    decorateClientCards(reachability);
    renderReachabilityControls(reachability);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
  }
};
