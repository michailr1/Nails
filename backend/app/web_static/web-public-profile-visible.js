renderPublicProfileSetup = function renderVisiblePublicProfile(reachability) {
  const page = document.querySelector("#page-content");
  const profile = reachability.public_profile || {};
  if (!page) return;

  const panel = document.createElement("section");
  panel.className = "panel client-public-profile-panel";
  const ready = Boolean(profile.ready);
  const displayName = profile.display_name || "";
  const publicContact = profile.public_contact || "";

  panel.innerHTML = ready
    ? `
      <p class="eyebrow">Профиль для клиенток</p>
      <h2>Как вас увидят клиентки</h2>
      <dl class="client-public-profile-summary">
        <div><dt>Имя мастера</dt><dd>${escapeHtml(displayName)}</dd></div>
        <div><dt>Контакт</dt><dd>${publicContact ? escapeHtml(publicContact) : "Не указан"}</dd></div>
      </dl>
      <button class="secondary-button" type="button" data-edit-public-profile>Изменить</button>
      <form id="client-public-profile-form" class="client-public-profile-form" hidden>
        <label><span>Имя мастера</span><input name="display_name" maxlength="160" required value="${escapeHtml(displayName)}"></label>
        <label><span>Контакт <small>необязательно</small></span><input name="public_contact" maxlength="160" value="${escapeHtml(publicContact)}" placeholder="Телефон или @username"></label>
        <p class="booking-edit-error" role="alert"></p>
        <div class="client-invite-actions">
          <button class="primary-button" type="submit">Сохранить</button>
          <button class="secondary-button" type="button" data-cancel-public-profile>Отмена</button>
        </div>
      </form>`
    : `
      <p class="eyebrow">Перед приглашением</p>
      <h2>Как вас увидят клиентки</h2>
      <p>Укажите имя мастера. Контакт необязателен — его клиентка увидит, если понадобится связаться напрямую.</p>
      <form id="client-public-profile-form" class="client-public-profile-form">
        <label><span>Имя мастера</span><input name="display_name" maxlength="160" required placeholder="Например, Настя"></label>
        <label><span>Контакт <small>необязательно</small></span><input name="public_contact" maxlength="160" placeholder="Телефон или @username"></label>
        <p class="booking-edit-error" role="alert"></p>
        <button class="primary-button" type="submit">Сохранить и продолжить</button>
      </form>`;

  page.prepend(panel);

  const form = panel.querySelector("form");
  const editButton = panel.querySelector("[data-edit-public-profile]");
  const cancelButton = panel.querySelector("[data-cancel-public-profile]");

  editButton?.addEventListener("click", () => {
    editButton.hidden = true;
    form.hidden = false;
    form.elements.display_name.focus();
  });
  cancelButton?.addEventListener("click", () => {
    form.elements.display_name.value = displayName;
    form.elements.public_contact.value = publicContact;
    form.querySelector(".booking-edit-error").textContent = "";
    form.hidden = true;
    editButton.hidden = false;
  });

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
      await renderClients();
    } catch (error) {
      if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
      errorLine.textContent = "Не удалось сохранить. Проверьте имя и попробуйте ещё раз.";
      button.disabled = false;
    }
  });
};
