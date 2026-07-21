const statisticsState = {
  mode: "month",
  dateFrom: null,
  dateTo: null,
};

const originalAppShellForStatistics = appShell;
appShell = function appShellWithStatistics(title, body) {
  originalAppShellForStatistics(title, body);
  const nav = document.querySelector(".nav");
  if (!nav || nav.querySelector('[data-view="statistics"]')) return;
  const button = document.createElement("button");
  button.className = `tab-button ${state.view === "statistics" ? "active" : ""}`;
  button.dataset.view = "statistics";
  button.type = "button";
  button.textContent = "Статистика";
  button.addEventListener("click", () => {
    state.view = "statistics";
    renderApp();
  });
  nav.append(button);
};

const originalRenderAppForStatistics = renderApp;
renderApp = async function renderAppWithStatistics() {
  if (state.view === "statistics") {
    clearPoll();
    try {
      await api("/web/api/auth/session");
    } catch (error) {
      if (error.status === 401) return renderLogin();
      return renderLogin("Не удалось проверить сессию.");
    }
    return renderStatistics();
  }
  return originalRenderAppForStatistics();
};

function statisticsRange(mode = statisticsState.mode) {
  const today = todayInTimezone(APP_TIMEZONE);
  if (mode === "day") return { dateFrom: today, dateTo: today };
  if (mode === "week") {
    const dateFrom = startOfWeek(today);
    return { dateFrom, dateTo: addDays(dateFrom, 6) };
  }
  if (mode === "custom" && statisticsState.dateFrom && statisticsState.dateTo) {
    return { dateFrom: statisticsState.dateFrom, dateTo: statisticsState.dateTo };
  }
  const dateFrom = `${today.slice(0, 7)}-01`;
  return { dateFrom, dateTo: endOfMonth(dateFrom) };
}

function formatMoney(value) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function statisticsModeSwitch() {
  return `<div class="mode-switch statistics-mode-switch" role="group" aria-label="Период статистики">
    ${[["day", "День"], ["week", "Неделя"], ["month", "Месяц"], ["custom", "Свой период"]]
      .map(([mode, label]) => `<button class="mode-button ${statisticsState.mode === mode ? "active" : ""}" data-statistics-mode="${mode}" type="button">${label}</button>`)
      .join("")}
  </div>`;
}

function statisticsCustomRange(range) {
  if (statisticsState.mode !== "custom") return "";
  return `<form id="statistics-range-form" class="statistics-range-form">
    <label>С даты<input name="date_from" type="date" value="${escapeHtml(range.dateFrom)}" required></label>
    <label>По дату<input name="date_to" type="date" value="${escapeHtml(range.dateTo)}" required></label>
    <button class="secondary-button" type="submit">Показать</button>
  </form>`;
}

function statisticCard(label, value, note = "") {
  return `<article class="panel statistic-card">
    <p class="eyebrow">${escapeHtml(label)}</p>
    <strong>${escapeHtml(value)}</strong>
    ${note ? `<p class="muted small">${escapeHtml(note)}</p>` : ""}
  </article>`;
}

function barRows(items, valueLabel) {
  if (!items.length) return '<p class="muted">Пока нет данных.</p>';
  const max = Math.max(...items.map((item) => item.visits_count || 0), 1);
  return `<div class="statistics-bars">${items.slice(0, 8).map((item) => `
    <div class="statistics-bar-row">
      <div class="statistics-bar-label"><span>${escapeHtml(item.name)}</span><strong>${escapeHtml(valueLabel(item))}</strong></div>
      <div class="statistics-bar-track" aria-hidden="true"><span style="width:${Math.max(6, Math.round((item.visits_count / max) * 100))}%"></span></div>
    </div>`).join("")}</div>`;
}

function revenueChart(days) {
  if (!days.some((day) => Number(day.revenue_amount) > 0)) {
    return '<p class="muted">Выручка появится после завершившихся записей.</p>';
  }
  const max = Math.max(...days.map((day) => Number(day.revenue_amount)), 1);
  return `<div class="revenue-chart" role="img" aria-label="Выручка по дням">
    ${days.map((day) => {
      const amount = Number(day.revenue_amount);
      const height = Math.max(amount > 0 ? 8 : 2, Math.round((amount / max) * 100));
      return `<div class="revenue-column" title="${escapeHtml(day.day)} — ${escapeHtml(formatMoney(amount))}">
        <span class="revenue-column-value">${amount ? escapeHtml(formatMoney(amount)) : ""}</span>
        <span class="revenue-column-bar" style="height:${height}%"></span>
        <span class="revenue-column-day">${escapeHtml(day.day.slice(8))}</span>
      </div>`;
    }).join("")}
  </div>`;
}

function clientRows(clients) {
  if (!clients.length) return '<p class="muted">Пока нет завершившихся визитов.</p>';
  return `<div class="statistics-client-list">${clients.slice(0, 10).map((client, index) => `
    <div class="statistics-client-row">
      <span class="statistics-rank">${index + 1}</span>
      <div><strong>${escapeHtml(client.client_name)}</strong><p class="muted small">${client.visits_count} визит(а) · средний чек ${client.average_check_amount === null ? "не определён" : escapeHtml(formatMoney(client.average_check_amount))}</p></div>
      <strong>${escapeHtml(formatMoney(client.revenue_amount))}</strong>
    </div>`).join("")}</div>`;
}

async function renderStatistics() {
  const range = statisticsRange();
  appShell("Статистика", `<div class="loading-state">Собираем понятную картину…</div>`);
  const actions = document.querySelector("#page-actions");
  actions.innerHTML = statisticsModeSwitch();
  document.querySelectorAll("[data-statistics-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      statisticsState.mode = button.dataset.statisticsMode;
      if (statisticsState.mode === "custom" && !statisticsState.dateFrom) {
        statisticsState.dateFrom = addDays(todayInTimezone(APP_TIMEZONE), -30);
        statisticsState.dateTo = todayInTimezone(APP_TIMEZONE);
      }
      renderStatistics();
    });
  });

  try {
    const payload = await api(`/web/api/statistics?date_from=${range.dateFrom}&date_to=${range.dateTo}`);
    const summary = payload.summary;
    document.querySelector("#page-content").innerHTML = `
      ${statisticsCustomRange(range)}
      <p class="statistics-period">${escapeHtml(dateLabel(range.dateFrom, { day: "numeric", month: "long", year: "numeric" }))} — ${escapeHtml(dateLabel(range.dateTo, { day: "numeric", month: "long", year: "numeric" }))}</p>
      <section class="statistics-cards">
        ${statisticCard("Выручка", formatMoney(summary.revenue_amount), summary.estimated_revenue_amount > 0 ? `Из неё предварительно ${formatMoney(summary.estimated_revenue_amount)}` : "По завершившимся записям")}
        ${statisticCard("Визиты", String(summary.visits_count), summary.assumed_visits_count ? `Без ручного уточнения: ${summary.assumed_visits_count}` : "Все результаты уточнены")}
        ${statisticCard("Средний чек", summary.average_check_amount === null ? "—" : formatMoney(summary.average_check_amount), summary.unknown_price_count ? `Без цены: ${summary.unknown_price_count}` : "По записям с известной ценой")}
        ${statisticCard("Клиентки", String(summary.unique_clients_count), `Отмены: ${summary.cancelled_count} · неявки: ${summary.no_show_count}`)}
      </section>
      <section class="statistics-grid">
        <article class="panel statistics-panel statistics-panel-wide"><div class="panel-header"><div><p class="eyebrow">Динамика</p><h2>Выручка по дням</h2></div></div>${revenueChart(payload.days)}</article>
        <article class="panel statistics-panel"><div class="panel-header"><div><p class="eyebrow">Чаще выбирают</p><h2>Процедуры</h2></div></div>${barRows(payload.procedures, (item) => `${item.visits_count} раз`)}</article>
        <article class="panel statistics-panel"><div class="panel-header"><div><p class="eyebrow">Дополняют запись</p><h2>Дополнения</h2></div></div>${barRows(payload.addons, (item) => `${item.visits_count} раз`)}</article>
        <article class="panel statistics-panel statistics-panel-wide"><div class="panel-header"><div><p class="eyebrow">Постоянные клиентки</p><h2>Клиентки по выручке</h2></div></div>${clientRows(payload.clients)}</article>
      </section>`;
    document.querySelector("#statistics-range-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      statisticsState.dateFrom = form.get("date_from");
      statisticsState.dateTo = form.get("date_to");
      if (statisticsState.dateTo < statisticsState.dateFrom) {
        window.alert("Дата окончания не может быть раньше даты начала.");
        return;
      }
      renderStatistics();
    });
  } catch (error) {
    if (error.status === 401) return renderLogin();
    document.querySelector("#page-content").innerHTML = '<div class="empty-state"><h2>Не удалось загрузить статистику</h2><p class="muted">Попробуйте обновить страницу.</p></div>';
  }
}
