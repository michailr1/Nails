renderPublicProfileSetup = function renderPublicProfileOutsideClients() {};

function masterPublicProfilePanel(profile = {}) {
  const ready = Boolean(profile.ready);
  const displayName = profile.display_name || "";
  const publicContact = profile.public_contact || "";
  return ready
    ? `
      <div class="master-settings-heading">
        <div><p class="eyebrow">Мастер</p><h2 id="master-profile-title">Как вас увидят клиентки</h2></div>
        <button class="ghost-button master-settings-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <p class="muted">Профиль для клиенток. Так вас видят при записи.</p>
      <dl class="client-public-profile-summary">
        <div><dt>Имя мастера</dt><dd>${escapeHtml(displayName)}</dd></div>
        <div><dt>Контакт</dt><dd>${publicContact ? escapeHtml(publicContact) : "Не указан"}</dd></div>
      </dl>
      <button class="secondary-button" type="button" data-edit-public-profile>Изменить</button>
      <form id="master-public-profile-form" class="client-public-profile-form" hidden>
        <label><span>Имя мастера</span><input name="display_name" maxlength="160" required value="${escapeHtml(displayName)}"></label>
        <label><span>Контакт <small>необязательно</small></span><input name="public_contact" maxlength="160" value="${escapeHtml(publicContact)}" placeholder="Телефон или @username"></label>
        <p class="booking-edit-error" role="alert"></p>
        <div class="master-settings-actions">
          <button class="primary-button" type="submit">Сохранить</button>
          <button class="secondary-button" type="button" data-cancel-public-profile>Отмена</button>
        </div>
      </form>`
    : `
      <div class="master-settings-heading">
        <div><p class="eyebrow">Перед приглашением</p><h2 id="master-profile-title">Как вас увидят клиентки</h2></div>
        <button class="ghost-button master-settings-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <p>Укажите имя мастера. Контакт необязателен — его клиентка увидит, если понадобится связаться напрямую.</p>
      <form id="master-public-profile-form" class="client-public-profile-form">
        <label><span>Имя мастера</span><input name="display_name" maxlength="160" required placeholder="Например, Настя"></label>
        <label><span>Контакт <small>необязательно</small></span><input name="public_contact" maxlength="160" placeholder="Телефон или @username"></label>
        <p class="booking-edit-error" role="alert"></p>
        <div class="master-settings-actions">
          <button class="primary-button" type="submit">Сохранить и продолжить</button>
          <button class="secondary-button" type="button" data-cancel-public-profile>Отмена</button>
        </div>
      </form>`;
}

async function renderMasterPublicProfile() {
  masterSettingsCloseDialog();
  const backdrop = document.createElement("div");
  backdrop.className = "master-settings-backdrop";
  backdrop.innerHTML = `
    <section class="panel master-settings-panel master-profile-panel" role="dialog" aria-modal="true" aria-labelledby="master-profile-title">
      <div class="master-settings-heading">
        <div><p class="eyebrow">Мастер</p><h2 id="master-profile-title">Как вас увидят клиентки</h2></div>
        <button class="ghost-button master-settings-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <p class="muted">Загружаем профиль…</p>
    </section>`;
  document.body.append(backdrop);
  const panel = backdrop.querySelector(".master-profile-panel");
  const bindClose = () => panel.querySelector(".master-settings-close")?.addEventListener("click", masterSettingsCloseDialog);
  bindClose();
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) masterSettingsCloseDialog();
  });

  try {
    const reachability = await api("/web/api/client-linking/reachability");
    const profile = reachability.public_profile || {};
    panel.innerHTML = masterPublicProfilePanel(profile);
    bindClose();

    const form = panel.querySelector("#master-public-profile-form");
    const editButton = panel.querySelector("[data-edit-public-profile]");
    const cancelButton = panel.querySelector("[data-cancel-public-profile]");
    editButton?.addEventListener("click", () => {
      editButton.hidden = true;
      form.hidden = false;
      form.elements.display_name.focus();
    });
    cancelButton?.addEventListener("click", masterSettingsCloseDialog);

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      const errorLine = form.querySelector(".booking-edit-error");
      button.disabled = true;
      errorLine.textContent = "";
      try {
        await api("/web/api/client-linking/public-profile", {
          method: "PUT",
          body: JSON.stringify({
            display_name: form.elements.display_name.value,
            public_contact: form.elements.public_contact.value || null,
          }),
        });
        masterSettingsCloseDialog();
      } catch (error) {
        if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
        errorLine.textContent = "Не удалось сохранить. Проверьте имя и попробуйте ещё раз.";
        button.disabled = false;
      }
    });
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    panel.innerHTML = `
      <div class="master-settings-heading">
        <h2 id="master-profile-title">Как вас увидят клиентки</h2>
        <button class="ghost-button master-settings-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <p class="booking-edit-error">Не удалось загрузить профиль.</p>`;
    bindClose();
  }
}
