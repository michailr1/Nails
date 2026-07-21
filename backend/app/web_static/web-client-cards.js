let webClientCards = [];
let webClientCardOpenId = null;
let webClientMessage = "";

const WEB_CLIENT_FIELD_LABELS = {
  public_name: "имя",
  phone: "телефон",
  contact_channel: "удобный способ связи",
  birthday: "день рождения",
  notes: "заметки",
  nail_skin_notes: "ногти и кожа",
  sensitivity_notes: "чувствительность",
  style_preferences: "предпочтения по стилю",
  communication_preferences: "предпочтения по общению",
};

function webClientValue(value) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function webClientOptional(value) {
  const normalized = String(value || "").trim();
  return normalized || null;
}

function webClientPayload(form) {
  return {
    public_name: String(form.elements.public_name.value || "").trim().replace(/\s+/g, " "),
    phone: webClientOptional(form.elements.phone.value),
    contact_channel: webClientOptional(form.elements.contact_channel.value),
    birthday: webClientOptional(form.elements.birthday.value),
    notes: webClientOptional(form.elements.notes.value),
    nail_skin_notes: webClientOptional(form.elements.nail_skin_notes.value),
    sensitivity_notes: webClientOptional(form.elements.sensitivity_notes.value),
    style_preferences: webClientOptional(form.elements.style_preferences.value),
    communication_preferences: webClientOptional(form.elements.communication_preferences.value),
  };
}

function webClientComparable(client) {
  return Object.fromEntries(
    Object.keys(WEB_CLIENT_FIELD_LABELS).map((field) => [field, webClientOptional(client[field])]),
  );
}

function webClientChangedFields(client, payload) {
  const current = webClientComparable(client);
  return Object.keys(WEB_CLIENT_FIELD_LABELS).filter((field) => current[field] !== payload[field]);
}

function webClientResultMatches(client, payload) {
  if (!client) return false;
  const returned = webClientComparable(client);
  return Object.keys(WEB_CLIENT_FIELD_LABELS).every((field) => returned[field] === payload[field]);
}

function webClientCompactDetails(client) {
  const details = [
    client.phone,
    client.contact_channel,
    client.style_preferences,
  ].filter(Boolean);
  return details.length ? details.slice(0, 2).join(" · ") : "Карточка пока почти пустая";
}

function webClientSummaryCard(client) {
  return `<article class="client-card client-card-summary ${webClientCardOpenId === client.client_id ? "active" : ""}">
    <button class="client-card-open" type="button" data-client-open="${escapeHtml(client.client_id)}">
      <span class="client-card-summary-main">
        <strong>${escapeHtml(client.public_name)}</strong>
        <small>${escapeHtml(webClientCompactDetails(client))}</small>
      </span>
      <span class="client-card-edit-label">Изменить</span>
    </button>
  </article>`;
}

function webClientEditor(client) {
  return `<section id="client-card-editor" class="panel client-card-editor">
    <div class="panel-header client-card-editor-header">
      <div><p class="eyebrow">Карточка клиентки</p><h2>${escapeHtml(client.public_name)}</h2></div>
      <button id="client-card-close" class="ghost-button" type="button">Закрыть</button>
    </div>
    <form id="client-card-form" class="client-card-form" data-client-id="${escapeHtml(client.client_id)}">
      <section class="client-card-section">
        <h3>Основное</h3>
        <div class="client-card-field-grid">
          <label class="client-card-field"><span>Имя</span><input name="public_name" type="text" maxlength="160" value="${escapeHtml(webClientValue(client.public_name))}" required></label>
          <label class="client-card-field"><span>Телефон</span><input name="phone" type="tel" maxlength="32" value="${escapeHtml(webClientValue(client.phone))}" placeholder="+7 …"></label>
          <label class="client-card-field"><span>День рождения</span><input name="birthday" type="date" value="${escapeHtml(webClientValue(client.birthday))}"></label>
          <label class="client-card-field"><span>Удобный способ связи</span><input name="contact_channel" type="text" maxlength="64" value="${escapeHtml(webClientValue(client.contact_channel))}" placeholder="Например, Telegram"></label>
        </div>
      </section>
      <section class="client-card-section">
        <h3>Что важно помнить</h3>
        <label class="client-card-field"><span>Общие заметки</span><textarea name="notes" maxlength="4000" rows="3" placeholder="Всё, что важно не забыть">${escapeHtml(webClientValue(client.notes))}</textarea></label>
      </section>
      <section class="client-card-section client-card-section-grid">
        <label class="client-card-field"><span>Ногти и кожа</span><textarea name="nail_skin_notes" maxlength="4000" rows="4" placeholder="Состояние ногтей, кожи, привычные материалы">${escapeHtml(webClientValue(client.nail_skin_notes))}</textarea></label>
        <label class="client-card-field"><span>Чувствительность</span><textarea name="sensitivity_notes" maxlength="4000" rows="4" placeholder="Аллергии, чувствительность, важные ограничения">${escapeHtml(webClientValue(client.sensitivity_notes))}</textarea></label>
        <label class="client-card-field"><span>Предпочтения по стилю</span><textarea name="style_preferences" maxlength="4000" rows="4" placeholder="Любимые цвета, форма, дизайн">${escapeHtml(webClientValue(client.style_preferences))}</textarea></label>
        <label class="client-card-field"><span>Предпочтения по общению</span><textarea name="communication_preferences" maxlength="2000" rows="4" placeholder="Например, обращаться на «вы»">${escapeHtml(webClientValue(client.communication_preferences))}</textarea></label>
      </section>
      <p id="client-card-status" class="client-card-status" role="status" aria-live="polite"></p>
      <div class="client-card-actions">
        <button id="client-card-cancel" class="secondary-button" type="button">Отмена</button>
        <button id="client-card-save" class="primary-button" type="submit">Сохранить изменения</button>
      </div>
    </form>
  </section>`;
}

function webClientRenderContent() {
  const content = document.querySelector("#page-content");
  if (!content) return;
  const opened = webClientCards.find((client) => client.client_id === webClientCardOpenId);
  content.innerHTML = `
    ${webClientMessage ? `<div class="info-note" role="status">${escapeHtml(webClientMessage)}</div>` : ""}
    ${opened ? webClientEditor(opened) : ""}
    ${webClientCards.length ? `<div class="client-grid client-card-list">${webClientCards.map(webClientSummaryCard).join("")}</div>` : `<div class="panel empty">Карточек клиенток пока нет.</div>`}`;
  webClientMessage = "";

  document.querySelectorAll("[data-client-open]").forEach((button) => {
    button.addEventListener("click", () => {
      webClientCardOpenId = button.dataset.clientOpen;
      webClientRenderContent();
      document.querySelector("#client-card-editor")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  document.querySelector("#client-card-close")?.addEventListener("click", () => {
    webClientCardOpenId = null;
    webClientRenderContent();
  });
  document.querySelector("#client-card-cancel")?.addEventListener("click", () => {
    webClientCardOpenId = null;
    webClientRenderContent();
  });
  document.querySelector("#client-card-form")?.addEventListener("submit", webClientSave);
}

function webClientErrorMessage(error) {
  const messages = {
    client_name_conflict: "Клиентка с таким именем уже есть. Выберите другое имя.",
    client_not_found: "Карточка больше не найдена. Обновляем список.",
  };
  return messages[error.message] || "Не удалось сохранить карточку. Проверьте данные и попробуйте ещё раз.";
}

async function webClientSave(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const clientId = form.dataset.clientId;
  const current = webClientCards.find((client) => client.client_id === clientId);
  if (!current) return;

  const payload = webClientPayload(form);
  if (!payload.public_name) {
    form.elements.public_name.focus();
    document.querySelector("#client-card-status").textContent = "Укажите имя клиентки.";
    return;
  }

  const changedFields = webClientChangedFields(current, payload);
  if (!changedFields.length) {
    document.querySelector("#client-card-status").textContent = "Изменений нет.";
    return;
  }

  const changedLabels = changedFields.map((field) => WEB_CLIENT_FIELD_LABELS[field]);
  const confirmation = [
    `Сохранить изменения в карточке «${current.public_name}»?`,
    "",
    `Изменится: ${changedLabels.join(", ")}.`,
  ].join("\n");
  if (!window.confirm(confirmation)) return;

  const save = document.querySelector("#client-card-save");
  const status = document.querySelector("#client-card-status");
  save.disabled = true;
  save.textContent = "Сохраняем…";
  status.textContent = "";

  try {
    const result = await api(`/web/api/clients/${encodeURIComponent(clientId)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    if (result?.client?.client_id !== clientId || !webClientResultMatches(result.client, payload)) {
      throw new Error("unverified_client_update");
    }
    const index = webClientCards.findIndex((client) => client.client_id === clientId);
    webClientCards[index] = result.client;
    webClientCards.sort((left, right) => left.public_name.localeCompare(right.public_name, "ru"));
    webClientCardOpenId = null;
    webClientMessage = result.changed ? "Карточка клиентки обновлена и проверена." : "Карточка уже содержала эти данные.";
    webClientRenderContent();
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    status.textContent = webClientErrorMessage(error);
    if (error.message === "client_not_found") {
      window.setTimeout(renderClients, 700);
      return;
    }
    save.disabled = false;
    save.textContent = "Сохранить изменения";
  }
}

renderClients = async function editableRenderClients() {
  appShell("Клиентки", `<div class="loading-state">Загружаем карточки…</div>`);
  const actions = document.querySelector("#page-actions");
  actions.innerHTML = `<button id="export-clients" class="secondary-button" type="button">Выгрузить всех клиенток</button>`;
  document.querySelector("#export-clients").addEventListener("click", () => {
    if (!window.confirm("В файл попадут все карточки клиенток со всеми заполненными полями. Выгрузить всех клиенток?")) return;
    downloadExport("/web/api/exports/clients?format=xlsx", `clients-all-${todayInTimezone(APP_TIMEZONE)}.xlsx`);
  });
  try {
    const data = await api("/web/api/clients");
    webClientCards = data.clients;
    if (!webClientCards.some((client) => client.client_id === webClientCardOpenId)) webClientCardOpenId = null;
    webClientRenderContent();
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    document.querySelector("#page-content").innerHTML = `<div class="panel error-state"><strong>Не удалось загрузить клиенток</strong><button id="retry" class="secondary-button">Повторить</button></div>`;
    document.querySelector("#retry").addEventListener("click", renderClients);
  }
};
