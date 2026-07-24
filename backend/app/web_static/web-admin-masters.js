(() => {
  let sessionRole = null;
  const baseRenderApp = renderApp;
  const baseAppShell = appShell;

  appShell = function adminAwareShell(title, body) {
    baseAppShell(title, body);
    if (sessionRole !== "admin") return;
    const nav = document.querySelector(".nav");
    if (!nav || nav.querySelector('[data-view="masters"]')) return;
    const button = document.createElement("button");
    button.className = `tab-button ${state.view === "masters" ? "active" : ""}`;
    button.dataset.view = "masters";
    button.type = "button";
    button.textContent = "Мастера";
    button.addEventListener("click", () => {
      state.view = "masters";
      renderApp();
    });
    nav.append(button);
  };

  async function resolveSessionRole() {
    try {
      await api("/web/api/admin/masters");
      return "admin";
    } catch (error) {
      if (error.status === 403) return "master";
      throw error;
    }
  }

  renderApp = async function adminAwareRenderApp() {
    clearPoll();
    try {
      await api("/web/api/auth/session");
      sessionRole = await resolveSessionRole();
    } catch (error) {
      if (error.status === 401) return renderLogin();
      return renderLogin("Не удалось проверить сессию.");
    }
    if (state.view === "masters") {
      if (sessionRole !== "admin") {
        state.view = "calendar";
        return baseRenderApp();
      }
      return renderMasters();
    }
    return baseRenderApp();
  };

  function onboardingLabel(status) {
    return {
      not_started: "Настройка не начата",
      in_progress: "Настройка продолжается",
      paused: "Настройка приостановлена",
      completed: "Настройка завершена",
    }[status] || "Состояние неизвестно";
  }

  function masterStatus(master) {
    if (!master.is_active) return "Доступ приостановлен";
    return master.onboarding_status === "completed" ? "Подключён" : "Настройка не завершена";
  }

  function maskTelegramId(value) {
    const text = String(value);
    if (text.length <= 4) return text;
    return `${text.slice(0, 2)}•••${text.slice(-2)}`;
  }

  async function renderMasters(message = "") {
    appShell("Мастера", `<div class="loading-state">Загружаем мастеров…</div>`);
    try {
      const payload = await api("/web/api/admin/masters");
      const cards = payload.masters.map((master) => `
        <article class="admin-master-card">
          <div>
            <p class="eyebrow">${escapeHtml(masterStatus(master))}</p>
            <h2>Мастер ${escapeHtml(maskTelegramId(master.telegram_user_id))}</h2>
          </div>
          <dl class="admin-master-meta">
            <div><dt>Telegram ID</dt><dd>${escapeHtml(maskTelegramId(master.telegram_user_id))}</dd></div>
            <div><dt>Первичная настройка</dt><dd>${escapeHtml(onboardingLabel(master.onboarding_status))}</dd></div>
          </dl>
        </article>`).join("");

      document.querySelector("#page-content").innerHTML = `
        <section class="admin-master-create">
          <p class="eyebrow">Новое подключение</p>
          <h2>Добавить мастера</h2>
          <p class="muted">Укажите Telegram ID. У мастера появится отдельный пустой кабинет.</p>
          ${message ? `<p class="small" role="status">${escapeHtml(message)}</p>` : ""}
          <form id="admin-master-form">
            <label>Telegram ID
              <input id="admin-master-telegram-id" inputmode="numeric" pattern="[0-9]+" required autocomplete="off" />
            </label>
            <button class="primary-button" type="submit">Добавить мастера</button>
          </form>
        </section>
        <section class="admin-master-list">
          <div class="section-heading"><p class="eyebrow">Подключённые аккаунты</p><h2>${payload.masters.length}</h2></div>
          ${cards || '<div class="empty-state">Мастеров пока нет.</div>'}
        </section>`;
      document.querySelector("#admin-master-form").addEventListener("submit", submitMaster);
    } catch (error) {
      if (error.status === 403) {
        state.view = "calendar";
        return baseRenderApp();
      }
      document.querySelector("#page-content").innerHTML = '<div class="empty-state">Не удалось загрузить список мастеров.</div>';
    }
  }

  async function submitMaster(event) {
    event.preventDefault();
    const input = document.querySelector("#admin-master-telegram-id");
    const telegramUserId = Number(input.value.trim());
    if (!Number.isSafeInteger(telegramUserId) || telegramUserId <= 0) {
      return renderMasters("Введите корректный Telegram ID.");
    }
    if (!window.confirm(`Добавить мастера с Telegram ID ${telegramUserId}? Будет создан отдельный пустой кабинет.`)) {
      return;
    }
    const button = event.currentTarget.querySelector("button[type=submit]");
    button.disabled = true;
    button.textContent = "Добавляем…";
    try {
      const result = await api("/web/api/admin/masters", {
        method: "POST",
        body: JSON.stringify({ telegram_user_id: telegramUserId }),
      });
      return renderMasters(result.created ? "Мастер добавлен." : "Этот мастер уже подключён.");
    } catch (error) {
      const message = error.status === 409
        ? "Этот Telegram ID уже принадлежит другой роли."
        : error.status === 403
          ? "Недостаточно прав."
          : "Не удалось добавить мастера.";
      return renderMasters(message);
    }
  }
})();
