function masterSettingsCloseMenu() {
  document.querySelector(".master-account-menu")?.remove();
}

function masterSettingsCloseDialog() {
  document.querySelector(".master-settings-backdrop")?.remove();
}

function masterSettingsAccountIcon() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>`;
}

function installMasterSettingsButton() {
  const host = document.querySelector(".topbar-side");
  if (!host || host.querySelector("[data-master-account]")) return;
  const wrapper = document.createElement("div");
  wrapper.className = "master-account";
  wrapper.innerHTML = `
    <button class="ghost-button master-account-button" type="button"
      data-master-account aria-label="Меню мастера" aria-expanded="false">
      ${masterSettingsAccountIcon()}
    </button>`;
  host.append(wrapper);

  const button = wrapper.querySelector("[data-master-account]");
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const existing = wrapper.querySelector(".master-account-menu");
    if (existing) {
      existing.remove();
      button.setAttribute("aria-expanded", "false");
      return;
    }
    masterSettingsCloseMenu();
    const menu = document.createElement("div");
    menu.className = "master-account-menu";
    menu.setAttribute("role", "menu");
    menu.innerHTML = `
      <button type="button" role="menuitem" data-open-master-settings>Настройки</button>`;
    wrapper.append(menu);
    button.setAttribute("aria-expanded", "true");
    const settingsButton = menu.querySelector("[data-open-master-settings]");
    settingsButton.addEventListener("click", () => {
      masterSettingsCloseMenu();
      button.setAttribute("aria-expanded", "false");
      renderMasterSettings();
    });
    settingsButton.focus();
  });
}

async function renderMasterSettings() {
  masterSettingsCloseDialog();
  const backdrop = document.createElement("div");
  backdrop.className = "master-settings-backdrop";
  backdrop.innerHTML = `
    <section class="panel master-settings-panel" role="dialog" aria-modal="true" aria-labelledby="master-settings-title">
      <div class="master-settings-heading">
        <div><p class="eyebrow">Мастер</p><h2 id="master-settings-title">Настройки</h2></div>
        <button class="ghost-button master-settings-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <p class="muted">Загружаем настройки…</p>
    </section>`;
  document.body.append(backdrop);
  const panel = backdrop.querySelector(".master-settings-panel");
  backdrop.querySelector(".master-settings-close").addEventListener("click", masterSettingsCloseDialog);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) masterSettingsCloseDialog();
  });

  try {
    const preferences = await api("/web/api/schedule/default-work-hours");
    const interval = (preferences.default_work_intervals || [])[0] || {};
    const startTime = String(interval.start_time || "10:00").slice(0, 5);
    const endTime = String(interval.end_time || "23:00").slice(0, 5);
    panel.innerHTML = `
      <div class="master-settings-heading">
        <div><p class="eyebrow">Мастер</p><h2 id="master-settings-title">Настройки</h2></div>
        <button class="ghost-button master-settings-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <form class="master-settings-form">
        <div class="master-setting-row">
          <div>
            <strong>Часовой пояс</strong>
            <p class="muted">В нём показываем календарь и время клиенткам.</p>
          </div>
          <span class="master-setting-value">${escapeHtml(state.timezone)}</span>
        </div>
        <div class="master-setting-row master-work-hours-row">
          <div>
            <strong>Обычные рабочие часы</strong>
            <p class="muted">Подсказки свободного времени на обычный день. Исключение на конкретную дату задаётся в Календаре и имеет приоритет.</p>
          </div>
          <div class="master-work-hours-fields">
            <label><span>С</span><input name="start_time" type="time" required value="${escapeHtml(startTime)}"></label>
            <label><span>До</span><input name="end_time" type="time" required value="${escapeHtml(endTime)}"></label>
          </div>
        </div>
        <p class="booking-edit-error" role="alert"></p>
        <div class="master-settings-actions">
          <button class="primary-button" type="submit">Сохранить</button>
          <button class="secondary-button" type="button" data-cancel-master-settings>Отмена</button>
        </div>
      </form>`;
    panel.querySelector(".master-settings-close").addEventListener("click", masterSettingsCloseDialog);
    panel.querySelector("[data-cancel-master-settings]").addEventListener("click", masterSettingsCloseDialog);
    const form = panel.querySelector("form");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const errorLine = form.querySelector(".booking-edit-error");
      const submit = form.querySelector("button[type='submit']");
      errorLine.textContent = "";
      if (form.elements.start_time.value >= form.elements.end_time.value) {
        errorLine.textContent = "Время окончания должно быть позже времени начала.";
        return;
      }
      submit.disabled = true;
      try {
        await api("/web/api/schedule/default-work-hours", {
          method: "PUT",
          body: JSON.stringify({
            intervals: [{
              start_time: form.elements.start_time.value,
              end_time: form.elements.end_time.value,
            }],
          }),
        });
        masterSettingsCloseDialog();
      } catch (error) {
        if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
        errorLine.textContent = "Не удалось сохранить рабочие часы. Проверьте время и попробуйте ещё раз.";
        submit.disabled = false;
      }
    });
    form.elements.start_time.focus();
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    panel.innerHTML = `
      <div class="master-settings-heading">
        <h2 id="master-settings-title">Настройки</h2>
        <button class="ghost-button master-settings-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <p class="booking-edit-error">Не удалось загрузить настройки.</p>`;
    panel.querySelector(".master-settings-close").addEventListener("click", masterSettingsCloseDialog);
  }
}

document.addEventListener("click", (event) => {
  if (!event.target.closest(".master-account")) {
    const button = document.querySelector("[data-master-account]");
    masterSettingsCloseMenu();
    button?.setAttribute("aria-expanded", "false");
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (document.querySelector(".master-settings-backdrop")) {
    masterSettingsCloseDialog();
    return;
  }
  const button = document.querySelector("[data-master-account]");
  masterSettingsCloseMenu();
  button?.setAttribute("aria-expanded", "false");
  button?.focus();
});

const appShellBeforeMasterSettings = appShell;
appShell = function appShellWithMasterSettings(title, body) {
  appShellBeforeMasterSettings(title, body);
  installMasterSettingsButton();
};
