function longAbsentRows(clients) {
  if (!clients.length) {
    return '<p class="muted statistics-empty">Сейчас таких клиенток нет.</p>';
  }
  return `<div class="long-absent-list">${clients.map((client) => `
    <div class="long-absent-row" data-long-absent-client-id="${escapeHtml(client.client_id)}">
      <div class="long-absent-copy">
        <strong>${escapeHtml(client.client_name)}</strong>
        <span>Последний раз ${escapeHtml(dateLabel(client.last_visit_date, { day: "numeric", month: "long", year: "numeric" }))} · ${escapeHtml(weeksSince(client.days_since_last_visit))} назад</span>
      </div>
      <div class="long-absent-actions">
        <button class="secondary-button" type="button" data-open-long-absent-client="${escapeHtml(client.client_id)}">Открыть карточку</button>
      </div>
    </div>`).join("")}</div>`;
}

function longAbsentPhoneUri(phone) {
  const normalized = String(phone || "")
    .trim()
    .replace(/[^+\d]/g, "")
    .replace(/(?!^)\+/g, "");
  return /^\+?\d{5,15}$/.test(normalized) ? `tel:${normalized}` : null;
}

async function openLongAbsentClient(clientId) {
  state.view = "clients";
  await renderClients();
  const exists = webClientCards.some((client) => client.client_id === clientId);
  if (!exists) return;
  webClientCreateOpen = false;
  webClientCardOpenId = clientId;
  webClientRenderContent();
  document.querySelector("#client-card-editor")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function enhanceLongAbsentActions() {
  const rows = [...document.querySelectorAll("[data-long-absent-client-id]")];
  if (!rows.length || state.view !== "statistics") return;

  document.querySelectorAll("[data-open-long-absent-client]").forEach((button) => {
    button.addEventListener("click", () => openLongAbsentClient(button.dataset.openLongAbsentClient));
  });

  try {
    const payload = await api("/web/api/clients");
    const directory = new Map((payload.clients || []).map((client) => [client.client_id, client]));
    rows.forEach((row) => {
      const client = directory.get(row.dataset.longAbsentClientId);
      const phoneUri = longAbsentPhoneUri(client?.phone);
      if (!client || !phoneUri) return;
      const actions = row.querySelector(".long-absent-actions");
      const link = document.createElement("a");
      link.className = "secondary-button long-absent-call";
      link.href = phoneUri;
      link.textContent = "Позвонить";
      link.setAttribute("aria-label", `Позвонить ${client.public_name}`);
      actions?.prepend(link);
    });
  } catch (error) {
    if (error.status === 401) renderLogin("Сессия завершилась. Войдите снова.");
  }
}

const renderStatisticsWithoutActions = renderStatistics;
renderStatistics = async function renderStatisticsWithActions() {
  await renderStatisticsWithoutActions();
  await enhanceLongAbsentActions();
};
