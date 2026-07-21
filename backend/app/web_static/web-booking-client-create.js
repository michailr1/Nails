function bookingClientNormalizeText(value) {
  return String(value || "").trim().replace(/\s+/g, " ");
}

function bookingClientErrorMessage(error) {
  const messages = {
    client_contact_conflict: "Клиентка с таким именем уже есть, но телефон отличается. Выберите её из списка; исправление карточки добавим следующим шагом.",
    client_profile_conflict: "Клиентка с таким именем уже есть. Выберите её из списка.",
  };
  return messages[error.message] || "Не удалось добавить клиентку. Проверьте имя и телефон.";
}

function bookingClientRemoveEmptyHint() {
  document.querySelectorAll("#booking-create-form .info-note").forEach((note) => {
    if (note.textContent.includes("Сначала добавьте клиентку")) note.remove();
  });
}

function bookingClientSelectCreated(client) {
  const select = document.querySelector('#booking-create-form select[name="client_public_name"]');
  if (!select) return;
  let option = [...select.options].find((item) => item.value === client.public_name);
  if (!option) {
    option = document.createElement("option");
    option.value = client.public_name;
    option.textContent = client.public_name;
    select.append(option);
  }
  select.value = client.public_name;
  select.dispatchEvent(new Event("change", { bubbles: true }));

  const submit = document.querySelector("#submit-booking-create");
  const hasBase = bookingComposerData?.services?.some(
    (service) => service.is_active && service.kind === "base",
  );
  if (submit && hasBase) submit.disabled = false;
  bookingClientRemoveEmptyHint();
}

async function bookingClientCreate() {
  const nameInput = document.querySelector("#booking-new-client-name");
  const phoneInput = document.querySelector("#booking-new-client-phone");
  const saveButton = document.querySelector("#booking-save-new-client");
  const status = document.querySelector("#booking-new-client-status");
  const publicName = bookingClientNormalizeText(nameInput?.value);
  const phone = bookingClientNormalizeText(phoneInput?.value) || null;

  if (!publicName) {
    nameInput?.focus();
    if (status) status.textContent = "Укажите имя клиентки.";
    return;
  }

  const confirmation = phone
    ? `Добавить клиентку «${publicName}» с телефоном ${phone}?`
    : `Добавить клиентку «${publicName}» без телефона?`;
  if (!window.confirm(confirmation)) return;

  if (saveButton) {
    saveButton.disabled = true;
    saveButton.textContent = "Добавляем…";
  }
  if (status) status.textContent = "";

  try {
    const result = await api("/web/api/clients", {
      method: "POST",
      body: JSON.stringify({ public_name: publicName, phone }),
    });
    const client = result?.client;
    if (!client || client.public_name !== publicName || client.profile_status !== "active") {
      throw new Error("unverified_client");
    }

    const existingIndex = bookingComposerData.clients.findIndex(
      (item) => item.client_id === client.client_id,
    );
    if (existingIndex >= 0) bookingComposerData.clients[existingIndex] = client;
    else bookingComposerData.clients.push(client);
    bookingComposerData.clients.sort((left, right) => left.public_name.localeCompare(right.public_name, "ru"));

    bookingClientSelectCreated(client);
    if (nameInput) nameInput.value = "";
    if (phoneInput) phoneInput.value = "";
    const panel = document.querySelector("#booking-new-client-panel");
    if (panel) panel.hidden = true;
    const toggle = document.querySelector("#booking-add-client-toggle");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
    if (status) {
      status.textContent = result.created
        ? "Клиентка добавлена и выбрана."
        : result.contact_added
          ? "Клиентка уже была в списке; телефон добавлен, клиентка выбрана."
          : "Клиентка уже была в списке — выбрали её.";
    }
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    if (status) status.textContent = bookingClientErrorMessage(error);
  } finally {
    if (saveButton?.isConnected) {
      saveButton.disabled = false;
      saveButton.textContent = "Добавить клиентку";
    }
  }
}

function bookingClientEnhanceComposer() {
  if (document.querySelector("#booking-client-field")) return;
  const select = document.querySelector('#booking-create-form select[name="client_public_name"]');
  const label = select?.closest("label");
  if (!select || !label) return;

  const wrapper = document.createElement("div");
  wrapper.id = "booking-client-field";
  wrapper.className = "booking-client-field";
  label.replaceWith(wrapper);
  wrapper.append(label);
  wrapper.insertAdjacentHTML("beforeend", `
    <button id="booking-add-client-toggle" class="ghost-button booking-add-client-toggle" type="button" aria-expanded="false" aria-controls="booking-new-client-panel">+ Новая клиентка</button>
    <div id="booking-new-client-panel" class="booking-new-client-panel" hidden>
      <label class="catalog-field"><span>Имя</span><input id="booking-new-client-name" type="text" maxlength="160" autocomplete="name" placeholder="Например, Марина"></label>
      <label class="catalog-field"><span>Телефон <em>необязательно</em></span><input id="booking-new-client-phone" type="tel" maxlength="32" autocomplete="tel" placeholder="+7 …"></label>
      <div class="booking-new-client-actions">
        <button id="booking-cancel-new-client" class="secondary-button" type="button">Отмена</button>
        <button id="booking-save-new-client" class="primary-button" type="button">Добавить клиентку</button>
      </div>
    </div>
    <p id="booking-new-client-status" class="booking-new-client-status" role="status" aria-live="polite"></p>`);

  const toggle = document.querySelector("#booking-add-client-toggle");
  const panel = document.querySelector("#booking-new-client-panel");
  toggle.addEventListener("click", () => {
    const opening = panel.hidden;
    panel.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
    if (opening) document.querySelector("#booking-new-client-name")?.focus();
  });
  document.querySelector("#booking-cancel-new-client").addEventListener("click", () => {
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  });
  document.querySelector("#booking-save-new-client").addEventListener("click", bookingClientCreate);
  document.querySelector("#booking-new-client-name").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      bookingClientCreate();
    }
  });
}

const originalBookingClientRenderComposer = renderBookingComposer;
renderBookingComposer = function bookingClientRenderComposer() {
  originalBookingClientRenderComposer();
  bookingClientEnhanceComposer();
};
