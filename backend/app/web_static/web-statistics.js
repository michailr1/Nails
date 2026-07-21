const statisticsState = {
  mode: "month",
  dateFrom: null,
  dateTo: null,
  focusLongAbsent: false,
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
    statisticsState.focusLongAbsent = false;
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
    ${[["day", "День"], ["week", "Неделя"], ["month", "Месяц"], ["custom", "Период"]]
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
    <span class="statistic-label">${escapeHtml(label)}</span>
    <strong>${escapeHtml(value)}</strong>
    ${note ? `<span class="statistic-note">${escapeHtml(note)}</span>` : ""}
  </article>`;
}

function barRows(items, valueLabel) {
  if (!items.length) return '<p class="muted statistics-empty">Пока нет данных.</p>';
  const max = Math.max(...items.map((item) => item.visits_count || 0), 1);
  return `<div class="statistics-bars">${items.slice(0, 6).map((item) => `
    <div class="statistics-bar-row">
      <div class="statistics-bar-label"><span>${escapeHtml(item.name)}</span><strong>${escapeHtml(valueLabel(item))}</strong></div>
      <div class="statistics-bar-track" aria-hidden="true"><span style="width:${Math.max(8, Math.round((item.visits_count / max) * 100))}%"></span></div>
    </div>`).join("")}</div>`;
}

function revenueChart(days) {
  const nonZero = days.filter((day) => Number(day.revenue_amount) > 0);
  if (!nonZero.length) {
    return '<p class="muted statistics-empty">За выбранный период выручки пока нет.</p>';
  }
  const max = Math.max(...days.map((day) => Number(day.revenue_amount)), 1);
  const labelStep = days.length > 20 ? 5 : days.length > 10 ? 2 : 1;
  return `<div class="revenue-chart-scroll"><div class="revenue-chart" role="img" aria-label="Выручка по дням">
    ${days.map((day, index) => {
      const amount = Number(day.revenue_amount);
      const height = Math.max(amount > 0 ? 10 : 2, Math.round((amount / max) * 100));
      const showLabel = index % labelStep === 0 || index === days.length - 1;
      return `<div class="revenue-column" title="${escapeHtml(day.day)} — ${escapeHtml(formatMoney(amount))}">
        <span class="revenue-column-bar" style="height:${height}%"></span>
        <span class="revenue-column-day">${showLabel ? escapeHtml(day.day.slice(8)) : ""}</span>
      </div>`;
    }).join("")}
  </div></div>`;
}

function clientRows(clients) {
  if (!clients.length) return '<p class="muted statistics-empty">Пока нет завершившихся визитов.</p>';
  return `<div class="statistics-client-list">${clients.slice(0, 8).map((client) => `
    <div class="statistics-client-row">
      <div class="statistics-client-main">
        <strong>${escapeHtml(client.client_name)}</strong>
        <span>${client.visits_count} визит(а) · средний чек ${client.average_check_amount === null ? "—" : escapeHtml(formatMoney(client.average_check_amount))}</span>
      </div>
      <strong class="statistics-client-total">${escapeHtml(formatMoney(client.revenue_amount))}</strong>
    </div>`).join("")}</div>`;
}

function weeksSince(days) {
  const weeks = Math.max(1, Math.floor(Number(days) / 7));
  return `${weeks} ${weeks % 10 === 1 && weeks % 100 !== 11 ? "неделю" : weeks % 10 >= 2 && weeks % 10 <= 4 && (weeks % 100 < 10 || weeks % 100 >= 20) ? "недели" : "недель"}`;
}

function longAbsentRows(clients) {
  if (!clients.length) {
    return '<p class="muted statistics-empty">Сейчас таких клиенток нет.</p>';
  }
  return `<div class="long-absent-list">${clients.map((client) => `
    <div class="long-absent-row">
      <strong>${escapeHtml(client.client_name)}</strong>
      <span>Последний раз ${escapeHtml(dateLabel(client.last_visit_date, { day: "numeric", month: "long", year: "numeric" }))} · ${escapeHtml(weeksSince(client.days_since_last_visit))} назад</span>
    </div>`).join("")}</div>`;
}

function statisticsNotice(summary) {
  const parts = [];
  if (summary.assumed_visits_count) parts.push(`${summary.assumed_visits_count} визит(а) учтены автоматически`);
  if (summary.unknown_price_count) parts.push(`${summary.unknown_price_count} визит(а) без известной цены`);
  if (!parts.length) return "";
  return `<p class="statistics-notice">${escapeHtml(parts.join(" · "))}</p>`;
}

function longAbsentInsightText(clients) {
  if (!clients.length) return "";
  const count = clients.length;
  const noun = count === 1 ? "клиентка давно не была" : count >= 2 && count <= 4 ? "клиентки давно не были" : "клиенток давно не были";
  return `${count} ${noun} — посмотреть`;
}

async function addLongAbsentCalendarInsight() {
  const page = document.querySelector("#page-content");
  if (!page || state.view !== "calendar") return;
  const today = todayInTimezone(APP_TIMEZONE);
  try {
    const payload = await api(`/web/api/statistics?date_from=${today}&date_to=${today}`);
    const clients = payload.long_absent_clients || [];
    if (!clients.length || state.view !== "calendar") return;
    const insight = document.createElement("button");
    insight.className = "naily-insight";
    insight.type = "button";
    insight.innerHTML = `<span class="naily-insight-label">Нэйли заметила</span><strong>${escapeHtml(longAbsentInsightText(clients))}</strong><span aria-hidden="true">→</span>`;
    insight.addEventListener("click", () => {
      statisticsState.focusLongAbsent = true;
      state.view = "statistics";
      renderApp();
    });
    page.prepend(insight);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
  }
}

const originalRenderCalendarForStatistics = renderCalendar;
renderCalendar = async function renderCalendarWithStatisticsInsight() {
  await originalRenderCalendarForStatistics();
  await addLongAbsentCalendarInsight();
};

async function renderStatistics() {
  const range = statisticsRange();
  appShell("Статистика", `<div class="loading-state">Загружаем статистику…</div>`);
  const actions = document.querySelector("#page-actions");
  actions.innerHTML = statisticsModeSwitch();
  document.querySelectorAll("[data-statistics-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      statisticsState.focusLongAbsent = false;
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
      <section id="long-absent" class="panel statistics-panel statistics-panel-wide long-absent-panel" tabindex="-1">
        <div class="statistics-section-title"><span>Нэйли подсказывает</span><h2>Давно не были</h2></div>
        ${longAbsentRows(payload.long_absent_clients || [])}
      </section>
      ${statisticsCustomRange(range)}
      <p class="statistics-period">${escapeHtml(dateLabel(range.dateFrom, { day: "numeric", month: "long", year: "numeric" }))} — ${escapeHtml(dateLabel(range.dateTo, { day: "numeric", month: "long", year: "numeric" }))}</p>
      <section class="statistics-cards">
        ${statisticCard("Выручка", formatMoney(summary.revenue_amount))}
        ${statisticCard("Визиты", String(summary.visits_count))}
        ${statisticCard("Средний чек", summary.average_check_amount === null ? "—" : formatMoney(summary.average_check_amount))}
        ${statisticCard("Клиентки", String(summary.unique_clients_count))}
      </section>
      ${statisticsNotice(summary)}
      <section class="statistics-grid">
        <article class="panel statistics-panel statistics-panel-wide"><div class="statistics-section-title"><span>Динамика</span><h2>Выручка по дням</h2></div>${revenueChart(payload.days)}</article>
        <article class="panel statistics-panel"><div class="statistics-section-title"><span>Популярность</span><h2>Процедуры</h2></div>${barRows(payload.procedures, (item) => `${item.visits_count}`)}</article>
        <article class="panel statistics-panel"><div class="statistics-section-title"><span>К записям</span><h2>Дополнения</h2></div>${barRows(payload.addons, (item) => `${item.visits_count}`)}</article>
        <article class="panel statistics-panel statistics-panel-wide"><div class="statistics-section-title"><span>Клиентки</span><h2>По выручке</h2></div>${clientRows(payload.clients)}</article>
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
    if (statisticsState.focusLongAbsent) {
      statisticsState.focusLongAbsent = false;
      const target = document.querySelector("#long-absent");
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      target?.focus({ preventScroll: true });
    }
  } catch (error) {
    if (error.status === 401) return renderLogin();
    document.querySelector("#page-content").innerHTML = '<div class="empty-state"><h2>Не удалось загрузить статистику</h2><p class="muted">Попробуйте обновить страницу.</p></div>';
  }
}
