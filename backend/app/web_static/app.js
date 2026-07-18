const app = document.querySelector("#app");
const state = {
  view: "calendar",
  selectedDate: todayInTimezone("Europe/Moscow"),
  challenge: null,
  pollTimer: null,
  offline: !navigator.onLine,
};

window.addEventListener("online", () => setOffline(false));
window.addEventListener("offline", () => setOffline(true));

function todayInTimezone(timeZone) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status === 401) {
    const error = new Error("unauthorized");
    error.status = 401;
    throw error;
  }
  if (!response.ok) {
    let code = `http_${response.status}`;
    try {
      const payload = await response.json();
      code = payload?.detail?.code || code;
    } catch {}
    const error = new Error(code);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

function clearPoll() {
  if (state.pollTimer) window.clearTimeout(state.pollTimer);
  state.pollTimer = null;
}

function setOffline(value) {
  state.offline = value;
  document.querySelector("#offline-banner")?.remove();
  if (value) {
    const banner = document.createElement("div");
    banner.id = "offline-banner";
    banner.className = "offline-banner";
    banner.textContent = "Нет соединения. Показываем последнее состояние.";
    document.body.append(banner);
  }
}

function authShell(content) {
  app.innerHTML = `
    <main class="center-shell">
      <header class="center-brand">
        <div class="brand">Нэйли</div>
        <p class="eyebrow">кабинет мастера</p>
      </header>
      <section class="auth-card">${content}</section>
      <footer class="auth-footer">Доступ только для подключённых мастеров</footer>
    </main>`;
  setOffline(state.offline);
}

function renderLogin(message = "") {
  clearPoll();
  authShell(`
    <p class="eyebrow">Без пароля</p>
    <h1>Войдите через Telegram</h1>
    <p class="muted">Мы покажем число для сверки и отправим запрос в закрытый бот. В Telegram достаточно нажать «Подтвердить».</p>
    ${message ? `<p class="small" role="alert">${escapeHtml(message)}</p>` : ""}
    <button id="login-button" class="primary-button" type="button">Войти через Telegram</button>
    <p class="muted small">Код вводить на сайте или в Telegram не нужно.</p>`);
  document.querySelector("#login-button").addEventListener("click", startLogin);
}

async function startLogin() {
  const button = document.querySelector("#login-button");
  button.disabled = true;
  button.textContent = "Создаём запрос…";
  try {
    state.challenge = await api("/web/api/auth/challenges", {
      method: "POST",
      body: JSON.stringify({}),
    });
    renderConfirmation();
    pollChallenge();
  } catch (error) {
    const message = error.status === 429
      ? "Слишком много попыток. Подождите немного и попробуйте снова."
      : error.status === 404 || error.status === 503
        ? "Веб-кабинет пока выключен администратором."
        : "Не удалось создать запрос на вход. Попробуйте ещё раз.";
    renderLogin(message);
  }
}

function renderConfirmation(statusText = "Ожидаем подтверждение в Telegram…") {
  const challenge = state.challenge;
  if (!challenge) return renderLogin();
  authShell(`
    <p class="eyebrow">Сверьте число</p>
    <h1>Подтвердите вход</h1>
    <p class="muted">В закрытом Telegram-боте появится запрос с тем же числом.</p>
    <div class="verification">
      <div class="verification-number" aria-label="Число для сверки">${escapeHtml(challenge.verification_number)}</div>
      <div class="status-line"><span class="spinner" aria-hidden="true"></span><span>${escapeHtml(statusText)}</span></div>
    </div>
    <button id="cancel-login" class="secondary-button" type="button">Начать заново</button>`);
  document.querySelector("#cancel-login").addEventListener("click", renderLogin);
}

async function pollChallenge() {
  if (!state.challenge) return;
  try {
    const current = await api(`/web/api/auth/challenges/${encodeURIComponent(state.challenge.challenge_id)}`);
    if (current.status === "approved") {
      renderConfirmation("Подтверждение получено. Открываем кабинет…");
      const result = await api("/web/api/auth/challenges/consume", {
        method: "POST",
        body: JSON.stringify({ challenge_id: state.challenge.challenge_id }),
      });
      if (result.authenticated) {
        state.challenge = null;
        clearPoll();
        return renderApp();
      }
    }
    if (["expired", "locked", "denied", "consumed"].includes(current.status)) {
      const messages = {
        expired: "Время подтверждения истекло.",
        locked: "Запрос заблокирован после нескольких попыток.",
        denied: "Вход отклонён в Telegram.",
        consumed: "Этот запрос уже использован.",
      };
      return renderLogin(messages[current.status]);
    }
    state.pollTimer = window.setTimeout(pollChallenge, 1800);
  } catch (error) {
    if (error.status === 404) return renderLogin("Запрос больше не действует. Начните вход заново.");
    state.pollTimer = window.setTimeout(pollChallenge, 3000);
  }
}

function appShell(title, body) {
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">Нэйли</div>
        <nav class="nav" aria-label="Разделы">
          <button class="tab-button ${state.view === "calendar" ? "active" : ""}" data-view="calendar">Календарь</button>
          <button class="tab-button ${state.view === "clients" ? "active" : ""}" data-view="clients">Клиентки</button>
        </nav>
        <div class="sidebar-bottom"><button id="logout" class="ghost-button" type="button">Выйти</button></div>
      </aside>
      <main class="main">
        <header class="topbar">
          <div><p class="eyebrow">Только просмотр</p><h1>${escapeHtml(title)}</h1></div>
          <div class="actions" id="page-actions"></div>
        </header>
        <section id="page-content">${body}</section>
      </main>
    </div>`;
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      renderApp();
    });
  });
  document.querySelector("#logout")?.addEventListener("click", logout);
  setOffline(state.offline);
}

async function renderApp() {
  clearPoll();
  try {
    await api("/web/api/auth/session");
  } catch (error) {
    if (error.status === 401) return renderLogin();
    return renderLogin("Не удалось проверить сессию.");
  }
  if (state.view === "clients") return renderClients();
  return renderCalendar();
}

function parseIsoDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day, 12));
}

function toIsoDate(date) {
  return date.toISOString().slice(0, 10);
}

function addDays(iso, count) {
  const date = parseIsoDate(iso);
  date.setUTCDate(date.getUTCDate() + count);
  return toIsoDate(date);
}

function dateLabel(iso, options) {
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "UTC", ...options }).format(parseIsoDate(iso));
}

function renderDateStrip() {
  const selected = state.selectedDate;
  const dates = Array.from({ length: 7 }, (_, index) => addDays(selected, index - 3));
  return `<div class="date-strip">${dates.map((iso) => `
    <button class="date-button ${iso === selected ? "active" : ""}" data-date="${iso}">
      ${escapeHtml(dateLabel(iso, { weekday: "short" }))}
      <strong>${escapeHtml(dateLabel(iso, { day: "numeric", month: "short" }))}</strong>
    </button>`).join("")}</div>`;
}

async function renderCalendar() {
  appShell("Календарь", `${renderDateStrip()}<div class="panel"><div class="loading-state">Загружаем записи…</div></div>`);
  const actions = document.querySelector("#page-actions");
  actions.innerHTML = `
    <button id="today" class="secondary-button" type="button">Сегодня</button>
    <button id="export-calendar" class="secondary-button" type="button">Экспорт XLSX</button>`;
  document.querySelectorAll("[data-date]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedDate = button.dataset.date;
      renderCalendar();
    });
  });
  document.querySelector("#today").addEventListener("click", () => {
    state.selectedDate = todayInTimezone("Europe/Moscow");
    renderCalendar();
  });
  document.querySelector("#export-calendar").addEventListener("click", () => downloadExport(
    `/web/api/exports/calendar?date_from=${state.selectedDate}&date_to=${state.selectedDate}&format=xlsx`,
    `calendar-${state.selectedDate}.xlsx`,
  ));
  try {
    const data = await api(`/web/api/calendar?date_from=${state.selectedDate}&date_to=${state.selectedDate}`);
    const content = document.querySelector("#page-content");
    content.innerHTML = `${renderDateStrip()}${calendarPanel(data)}`;
    content.querySelectorAll("[data-date]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedDate = button.dataset.date;
        renderCalendar();
      });
    });
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    document.querySelector("#page-content").innerHTML = `${renderDateStrip()}<div class="panel error-state"><strong>Не удалось загрузить календарь</strong><button id="retry" class="secondary-button">Повторить</button></div>`;
    document.querySelector("#retry").addEventListener("click", renderCalendar);
  }
}

function calendarPanel(data) {
  const title = dateLabel(state.selectedDate, { weekday: "long", day: "numeric", month: "long" });
  if (!data.bookings.length) {
    return `<div class="panel"><div class="panel-header"><h2>${escapeHtml(title)}</h2><span class="muted small">${escapeHtml(data.timezone)}</span></div><div class="empty">На этот день записей нет.</div></div>`;
  }
  return `<div class="panel">
    <div class="panel-header"><h2>${escapeHtml(title)}</h2><span class="muted small">${data.bookings.length} записей</span></div>
    <div class="list">${data.bookings.map((booking) => {
      const start = new Date(booking.starts_at);
      const end = new Date(booking.ends_at);
      const format = new Intl.DateTimeFormat("ru-RU", { timeZone: data.timezone, hour: "2-digit", minute: "2-digit" });
      return `<article class="booking">
        <div class="time">${escapeHtml(format.format(start))}</div>
        <div><h3>${escapeHtml(booking.client_name)}</h3><p>${escapeHtml(booking.service_name)} · до ${escapeHtml(format.format(end))}</p><span class="badge">${escapeHtml(booking.status)}</span></div>
        <div class="price">${escapeHtml(formatMoney(booking.price_amount, booking.currency))}</div>
      </article>`;
    }).join("")}</div>
  </div>`;
}

function formatMoney(amount, currency) {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(amount));
}

async function renderClients() {
  appShell("Клиентки", `<div class="loading-state">Загружаем карточки…</div>`);
  const actions = document.querySelector("#page-actions");
  actions.innerHTML = `<button id="export-clients" class="secondary-button" type="button">Экспорт XLSX</button>`;
  document.querySelector("#export-clients").addEventListener("click", () => downloadExport(
    "/web/api/exports/clients?format=xlsx",
    "clients.xlsx",
  ));
  try {
    const data = await api("/web/api/clients");
    document.querySelector("#page-content").innerHTML = data.clients.length
      ? `<div class="client-grid">${data.clients.map(clientCard).join("")}</div>`
      : `<div class="panel empty">Карточек клиенток пока нет.</div>`;
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    document.querySelector("#page-content").innerHTML = `<div class="panel error-state"><strong>Не удалось загрузить клиенток</strong><button id="retry" class="secondary-button">Повторить</button></div>`;
    document.querySelector("#retry").addEventListener("click", renderClients);
  }
}

function clientCard(client) {
  const fields = [
    ["Телефон", client.phone],
    ["Канал связи", client.contact_channel],
    ["День рождения", client.birthday],
    ["Заметки", client.notes],
    ["Ногти и кожа", client.nail_skin_notes],
    ["Чувствительность", client.sensitivity_notes],
    ["Стиль", client.style_preferences],
    ["Общение", client.communication_preferences],
  ].filter(([, value]) => value);
  return `<article class="client-card">
    <h3>${escapeHtml(client.public_name)}</h3>
    <p>${escapeHtml(client.profile_status)}</p>
    ${fields.length ? `<dl>${fields.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl>` : `<p class="small">Дополнительных данных нет.</p>`}
  </article>`;
}

async function downloadExport(path, filename) {
  try {
    const response = await fetch(path, { method: "POST", credentials: "same-origin", cache: "no-store" });
    if (response.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    if (!response.ok) throw new Error("export_failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch {
    window.alert("Не удалось подготовить файл. Попробуйте ещё раз.");
  }
}

async function logout() {
  try {
    await api("/web/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
  } catch {}
  renderLogin();
}

renderApp();
