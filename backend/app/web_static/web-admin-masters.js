(() => {
  let sessionRole = null;
  let targetOwnerUserId = null;
  let selectedMaster = null;
  const baseRenderApp = renderApp;
  const baseAppShell = appShell;

  function maskTelegramId(value) {
    const text = String(value);
    if (text.length <= 4) return text;
    return `${text.slice(0, 2)}•••${text.slice(-2)}`;
  }

  appShell = function adminAwareShell(title, body) {
    const scopeBanner = sessionRole === "admin" && selectedMaster
      ? `<div class="admin-scope-banner" role="status">Просмотр как мастер ${escapeHtml(maskTelegramId(selectedMaster.telegram_user_id))} · только чтение</div>`
      : "";
    baseAppShell(title, `${scopeBanner}${body}`);
    document.body.classList.toggle("admin-readonly", sessionRole === "admin" && Boolean(targetOwnerUserId));
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

  async function loadMasters() {
    const payload = await api("/web/api/admin/masters");
    selectedMaster = payload.masters.find((master) => master.id === targetOwnerUserId) || null;
    return payload.masters;
  }

  renderApp = async function adminAwareRenderApp() {
    clearPoll();
    try {
      const session = await api("/web/api/auth/session");
      sessionRole = session.role;
      targetOwnerUserId = session.target_owner_user_id || null;
      if (sessionRole === "admin") await loadMasters();
    } catch (error) {
      if (error.status === 401) return renderLogin();
      return renderLogin("Не удалось проверить сессию.");
    }
    if (sessionRole === "admin" && !targetOwnerUserId) {
      state.view = "masters";
      return renderMasters("Выберите мастера для просмотра кабинета.");
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

  function masterActions(master) {
    if (!master.is_active) {
      return `<button class="primary-button admin-reactivate-master" type="button" data-master-id="${escapeHtml(master.id)}" data-telegram-id="${escapeHtml(master.telegram_user_id)}">Вернуть доступ</button>`;
    }
    return `
      <button class="secondary-button admin-select-master" type="button" data-master-id="${escapeHtml(master.id)}">
        ${master.id === targetOwnerUserId ? "Открыт сейчас" : "Открыть обзор"}
      </button>
      <button class="secondary-button admin-disable-master" type="button" data-master-id="${escapeHtml(master.id)}" data-telegram-id="${escapeHtml(master.telegram_user_id)}">Отключить мастера</button>`;
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
          <div class="admin-master-actions">${masterActions(master)}</div>
        </article>`).join("");

      document.querySelector("#page-content").innerHTML = `
        <section class="admin-master-create">
          <p class="eyebrow">Новое подключение</p>
          <h2>Добавить мастера</h2>
          <p class="muted">Укажите Telegram ID. Нэйли создаст кабинет и сразу откроет доступ к помощнице.</p>
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
      document.querySelectorAll(".admin-select-master").forEach((button) => {
        button.addEventListener("click", () => selectMaster(button.dataset.masterId));
      });
      document.querySelectorAll(".admin-disable-master").forEach((button) => {
        button.addEventListener("click", () => disableMaster(button.dataset.masterId, button.dataset.telegramId));
      });
      document.querySelectorAll(".admin-reactivate-master").forEach((button) => {
        button.addEventListener("click", () => reactivateMaster(button.dataset.telegramId));
      });
    } catch (error) {
      if (error.status === 403) {
        state.view = "calendar";
        return baseRenderApp();
      }
      document.querySelector("#page-content").innerHTML = '<div class="empty-state">Не удалось загрузить список мастеров.</div>';
    }
  }

  async function selectMaster(masterUserId) {
    try {
      const result = await api("/web/api/admin/select-master", {
        method: "POST",
        body: JSON.stringify({ master_user_id: masterUserId }),
      });
      targetOwnerUserId = result.master.id;
      selectedMaster = result.master;
      state.view = "calendar";
      return renderApp();
    } catch (error) {
      const message = error.status === 404
        ? "Мастер не найден или его доступ приостановлен."
        : error.status === 403
          ? "Недостаточно прав."
          : "Не удалось открыть кабинет мастера.";
      return renderMasters(message);
    }
  }

  async function disableMaster(masterUserId, telegramUserId) {
    if (!window.confirm(`Отключить мастера ${maskTelegramId(telegramUserId)}? Данные и записи сохранятся, но доступ к Нэйли будет отозван.`)) return;
    try {
      await api(`/web/api/admin/masters/${masterUserId}/disable`, { method: "POST" });
      if (targetOwnerUserId === masterUserId) {
        targetOwnerUserId = null;
        selectedMaster = null;
      }
      return renderMasters("Доступ мастера отключён. Данные сохранены.");
    } catch (error) {
      return renderMasters(error.status === 503
        ? "Не удалось применить доступ в Hermes. Изменения не завершены."
        : "Не удалось отключить мастера.");
    }
  }

  async function reactivateMaster(telegramUserId) {
    if (!window.confirm(`Вернуть доступ мастеру ${maskTelegramId(telegramUserId)}?`)) return;
    try {
      const result = await api("/web/api/admin/masters", {
        method: "POST",
        body: JSON.stringify({ telegram_user_id: Number(telegramUserId) }),
      });
      return renderMasters(result.reactivated ? "Доступ мастера восстановлен." : "Мастер уже подключён.");
    } catch (error) {
      return renderMasters(error.status === 503
        ? "Не удалось применить доступ в Hermes. Изменения не завершены."
        : "Не удалось вернуть доступ мастеру.");
    }
  }

  async function submitMaster(event) {
    event.preventDefault();
    const input = document.querySelector("#admin-master-telegram-id");
    const telegramUserId = Number(input.value.trim());
    if (!Number.isSafeInteger(telegramUserId) || telegramUserId <= 0) {
      return renderMasters("Введите корректный Telegram ID.");
    }
    if (!window.confirm(`Добавить мастера с Telegram ID ${telegramUserId}? Будет создан отдельный пустой кабинет и открыт доступ к Нэйли.`)) {
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
      return renderMasters(result.created
        ? "Мастер добавлен и получил доступ к Нэйли."
        : result.reactivated
          ? "Доступ мастера восстановлен."
          : "Этот мастер уже подключён.");
    } catch (error) {
      const message = error.status === 409
        ? "Этот Telegram ID уже принадлежит другой роли."
        : error.status === 403
          ? "Недостаточно прав."
          : error.status === 503
            ? "Не удалось применить доступ в Hermes. Мастер не добавлен."
            : "Не удалось добавить мастера.";
      return renderMasters(message);
    }
  }
})();
