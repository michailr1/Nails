let serviceCatalogDraft = [];
let serviceCatalogOriginal = [];
let expandedServiceIndex = null;
let removedCatalogExpanded = false;

const SERVICE_CATEGORY_PRESETS = [
  "Маникюр",
  "Педикюр",
  "Дополнительно",
  "Дизайн",
  "Парафинотерапия",
];

function cloneCatalog(services) {
  return services.map((service) => ({ ...service }));
}

function catalogNumber(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  return Number(value);
}

function catalogNullableNumber(value) {
  return value === null || value === undefined || value === "" ? null : Number(value);
}

function emptyCatalogService() {
  return {
    public_name: "",
    public_description: null,
    price_amount: 0,
    currency: "RUB",
    duration_minutes: 60,
    buffer_before_minutes: 0,
    buffer_after_minutes: 0,
    is_active: true,
    kind: "base",
    price_type: "fixed",
    price_min_amount: null,
    price_max_amount: null,
    price_unit: null,
    category: null,
    sort_order: serviceCatalogDraft.length,
    extra_minutes: 0,
    is_new: true,
  };
}

function catalogField(service, index, name, label, type = "text", help = "", optional = false) {
  const value = service[name] ?? "";
  return `<label class="catalog-field"><span>${escapeHtml(label)}${optional ? ' <em>необязательно</em>' : ""}</span><input data-service-index="${index}" data-service-field="${name}" type="${type}" value="${escapeHtml(value)}">${help ? `<small>${escapeHtml(help)}</small>` : ""}</label>`;
}

function catalogSelect(service, index, name, label, options, help = "") {
  const items = options.map(([value, title]) => `<option value="${value}" ${service[name] === value ? "selected" : ""}>${title}</option>`).join("");
  return `<label class="catalog-field"><span>${escapeHtml(label)}</span><select data-service-index="${index}" data-service-field="${name}">${items}</select>${help ? `<small>${escapeHtml(help)}</small>` : ""}</label>`;
}

function catalogCategoryField(service, index) {
  const listId = `service-category-${index}`;
  const options = SERVICE_CATEGORY_PRESETS.map((category) => `<option value="${escapeHtml(category)}"></option>`).join("");
  return `<label class="catalog-field"><span>Раздел прайса <em>необязательно</em></span><input data-service-index="${index}" data-service-field="category" type="text" list="${listId}" value="${escapeHtml(service.category ?? "")}" placeholder="Выберите раздел или напишите свой"><datalist id="${listId}">${options}</datalist><small>Помогает собрать позиции в понятные разделы. Можно выбрать готовый раздел или написать свой.</small></label>`;
}

function servicePriceFields(service, index) {
  if (service.price_type === "range") {
    return `${catalogField(service, index, "price_min_amount", "Цена от, ₽", "number", "Нижняя граница стоимости.")}${catalogField(service, index, "price_max_amount", "Цена до, ₽", "number", "Верхняя граница стоимости.")}`;
  }
  if (service.price_type === "per_unit") {
    return `${catalogField(service, index, "price_amount", "Цена, ₽", "number", "Стоимость одной единицы.")}${catalogField(service, index, "price_unit", "За что цена", "text", "Например: за ноготь или за минуту.")}`;
  }
  if (service.price_type === "fixed") {
    return catalogField(service, index, "price_amount", "Цена, ₽", "number", "Полная стоимость позиции.");
  }
  return "";
}

function serviceEditorCard(service, index) {
  const timeFields = service.kind === "addon"
    ? catalogField(service, index, "extra_minutes", "Доп. время, мин", "number", "Насколько дополнение увеличивает запись.", true)
    : `${catalogField(service, index, "duration_minutes", "Сколько обычно занимает, мин", "number", "Ориентировочное время процедуры.")}${catalogField(service, index, "buffer_after_minutes", "Оставить время после, мин", "number", "На уборку, подготовку или перерыв.", true)}`;
  return `<article class="panel catalog-card catalog-card-editing" data-service-card="${index}">
    <div class="panel-header">
      <strong>${escapeHtml(service.public_name || "Новая позиция")}</strong>
      <button class="ghost-button catalog-remove" data-remove-service="${index}" type="button">${service.is_new ? "Удалить" : "Убрать из прайса"}</button>
    </div>
    <div class="catalog-grid">
      ${catalogField(service, index, "public_name", "Название", "text", "Так позиция будет показана в прайсе и записях.")}
      ${catalogField(service, index, "public_description", "Описание", "text", "Короткое пояснение для мастера.", true)}
      ${catalogSelect(service, index, "kind", "Позиция в записи", [["base", "Основная процедура"], ["addon", "Дополнение"]], "Дополнение добавляется к основной процедуре.")}
      ${catalogSelect(service, index, "price_type", "Как указана цена", [["fixed", "Фиксированная"], ["range", "Диапазон"], ["per_unit", "За единицу"], ["on_request", "По запросу"]], "Поля цены появятся только когда они нужны.")}
      ${servicePriceFields(service, index)}
      ${timeFields}
      ${catalogCategoryField(service, index)}
    </div>
  </article>`;
}

function catalogPriceSummary(service) {
  const amount = (value) => `${Number(value || 0).toLocaleString("ru-RU")} ₽`;
  if (service.price_type === "range") return `${amount(service.price_min_amount)}–${amount(service.price_max_amount)}`;
  if (service.price_type === "on_request") return "Цена после уточнения";
  if (service.price_type === "per_unit") return `${amount(service.price_amount)}${service.price_unit ? ` / ${escapeHtml(service.price_unit)}` : ""}`;
  return amount(service.price_amount);
}

function catalogTimeSummary(service) {
  const minutes = service.kind === "addon" ? service.extra_minutes : service.duration_minutes;
  if (!minutes) return "Время не указано";
  const hours = Math.floor(Number(minutes) / 60);
  const remainder = Number(minutes) % 60;
  if (!hours) return `${remainder} мин`;
  return remainder ? `${hours} ч ${remainder} мин` : `${hours} ч`;
}

function serviceSummaryCard(service, index) {
  return `<article class="panel catalog-card catalog-card-summary" data-service-card="${index}">
    <div class="catalog-summary-main">
      <strong>${escapeHtml(service.public_name)}</strong>
      <span>${catalogPriceSummary(service)}</span>
      <small>${catalogTimeSummary(service)}${service.kind === "addon" ? " · дополнение" : ""}</small>
    </div>
    <div class="catalog-summary-actions">
      <button class="secondary-button" data-edit-service="${index}" type="button">Изменить</button>
      <button class="ghost-button catalog-remove" data-remove-service="${index}" type="button">Убрать из прайса</button>
    </div>
  </article>`;
}

function catalogGroups() {
  const groups = new Map();
  serviceCatalogDraft.forEach((service, index) => {
    const category = String(service.category || "").trim() || "Без раздела";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push({ service, index });
  });
  const order = new Map(SERVICE_CATEGORY_PRESETS.map((category, index) => [category, index]));
  return [...groups.entries()].sort(([left], [right]) => {
    const leftOrder = left === "Без раздела" ? -1 : (order.get(left) ?? SERVICE_CATEGORY_PRESETS.length);
    const rightOrder = right === "Без раздела" ? -1 : (order.get(right) ?? SERVICE_CATEGORY_PRESETS.length);
    return leftOrder - rightOrder || left.localeCompare(right, "ru");
  });
}

function removedCatalogServices() {
  const draftNames = new Set(serviceCatalogDraft.map((service) => service.public_name));
  return serviceCatalogOriginal.filter((service) => !draftNames.has(service.public_name));
}

function renderRemovedCatalog() {
  const removed = removedCatalogServices();
  if (!removed.length) return "";
  return `<details class="panel catalog-removed" ${removedCatalogExpanded ? "open" : ""}>
    <summary>Убрано из прайса · ${removed.length}</summary>
    <div class="catalog-removed-list">${removed.map((service) => `<div class="catalog-removed-item">
      <div><strong>${escapeHtml(service.public_name)}</strong><small>${escapeHtml(service.category || "Без раздела")}</small></div>
      <button class="secondary-button" data-restore-service="${escapeHtml(service.public_name)}" type="button">Вернуть в прайс</button>
    </div>`).join("")}</div>
  </details>`;
}

function renderCatalogList() {
  if (!serviceCatalogDraft.length) return '<div class="panel empty">В прайсе пока нет позиций.</div>';
  return catalogGroups().map(([category, items]) => `<section class="catalog-section">
    <h2>${escapeHtml(category)}</h2>
    <div class="catalog-section-list">${items.map(({ service, index }) => (
      index === expandedServiceIndex ? serviceEditorCard(service, index) : serviceSummaryCard(service, index)
    )).join("")}</div>
  </section>`).join("");
}

function bindCatalogFields() {
  document.querySelectorAll("[data-service-field]").forEach((control) => {
    control.addEventListener("change", () => {
      const service = serviceCatalogDraft[Number(control.dataset.serviceIndex)];
      const field = control.dataset.serviceField;
      service[field] = control.type === "checkbox" ? control.checked : control.value;
      if (field === "kind") {
        if (service.kind === "addon") {
          service.duration_minutes = null;
          service.buffer_before_minutes = 0;
          service.buffer_after_minutes = 0;
        } else {
          service.duration_minutes ||= 60;
          service.extra_minutes = 0;
        }
        renderServiceCatalogBody();
      }
      if (field === "price_type" || field === "is_active") renderServiceCatalogBody();
    });
  });
}

function renderServiceCatalogBody(message = "") {
  const content = document.querySelector("#page-content");
  if (!content) return;
  content.innerHTML = `${message ? `<div class="info-note" role="status">${escapeHtml(message)}</div>` : ""}
    <div class="info-note">Здесь только позиции, которые сейчас входят в прайс. Изменения применяются после проверки и подтверждения.</div>
    <div class="catalog-actions"><button id="add-service" class="secondary-button" type="button">Добавить в прайс</button><button id="save-catalog" class="primary-button" type="button">Проверить и сохранить</button></div>
    <div class="catalog-list">${renderCatalogList()}</div>
    ${renderRemovedCatalog()}`;
  document.querySelector("#add-service").addEventListener("click", () => {
    serviceCatalogDraft.unshift(emptyCatalogService());
    expandedServiceIndex = 0;
    renderServiceCatalogBody();
    const nameInput = document.querySelector('[data-service-index="0"][data-service-field="public_name"]');
    nameInput?.scrollIntoView({ behavior: "smooth", block: "center" });
    nameInput?.focus({ preventScroll: true });
  });
  document.querySelector("#save-catalog").addEventListener("click", saveServiceCatalog);
  document.querySelectorAll("[data-edit-service]").forEach((button) => {
    button.addEventListener("click", () => {
      expandedServiceIndex = Number(button.dataset.editService);
      renderServiceCatalogBody();
      document.querySelector(`[data-service-card="${expandedServiceIndex}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  document.querySelectorAll("[data-remove-service]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.removeService);
      serviceCatalogDraft.splice(index, 1);
      expandedServiceIndex = null;
      renderServiceCatalogBody(serviceCatalogDraft.length ? "Позиция убрана. Проверьте изменения и сохраните прайс." : "Прайс пуст. Добавьте хотя бы одну позицию перед сохранением.");
    });
  });
  document.querySelector(".catalog-removed")?.addEventListener("toggle", (event) => {
    removedCatalogExpanded = event.currentTarget.open;
  });
  document.querySelectorAll("[data-restore-service]").forEach((button) => {
    button.addEventListener("click", () => {
      const original = serviceCatalogOriginal.find((service) => service.public_name === button.dataset.restoreService);
      if (!original) return;
      serviceCatalogDraft.unshift({ ...original, is_active: true });
      expandedServiceIndex = null;
      removedCatalogExpanded = true;
      renderServiceCatalogBody("Позиция возвращена. Проверьте изменения и сохраните прайс.");
    });
  });
  bindCatalogFields();
}

function normalizeCatalogService(service) {
  const kind = service.kind || "base";
  const priceType = service.price_type || "fixed";
  return {
    public_name: String(service.public_name || "").trim(),
    public_description: String(service.public_description || "").trim() || null,
    price_amount: priceType === "fixed" || priceType === "per_unit" ? catalogNullableNumber(service.price_amount) : null,
    currency: "RUB",
    duration_minutes: kind === "base" ? catalogNullableNumber(service.duration_minutes) : null,
    buffer_before_minutes: kind === "base" ? catalogNumber(service.buffer_before_minutes) : 0,
    buffer_after_minutes: kind === "base" ? catalogNumber(service.buffer_after_minutes) : 0,
    is_active: true,
    kind,
    price_type: priceType,
    price_min_amount: priceType === "range" ? catalogNullableNumber(service.price_min_amount) : null,
    price_max_amount: priceType === "range" ? catalogNullableNumber(service.price_max_amount) : null,
    price_unit: priceType === "per_unit" ? String(service.price_unit || "").trim() || null : null,
    category: String(service.category || "").trim() || null,
    sort_order: catalogNumber(service.sort_order),
    extra_minutes: kind === "addon" ? catalogNumber(service.extra_minutes) : 0,
  };
}

function catalogDiffSummary(future) {
  const originalByName = new Map(serviceCatalogOriginal.map((item) => [item.public_name, item]));
  const futureNames = new Set(future.map((item) => item.public_name));
  const created = future.filter((item) => !originalByName.has(item.public_name)).map((item) => item.public_name);
  const changed = future.filter((item) => {
    const original = originalByName.get(item.public_name);
    return original && original.is_active && JSON.stringify(normalizeCatalogService(original)) !== JSON.stringify(item);
  }).map((item) => item.public_name);
  const archived = serviceCatalogOriginal.filter((item) => item.is_active && !futureNames.has(item.public_name)).map((item) => item.public_name);
  const restored = serviceCatalogOriginal.filter((item) => !item.is_active && futureNames.has(item.public_name)).map((item) => item.public_name);
  return [
    created.length ? `Добавить: ${created.join(", ")}` : null,
    changed.length ? `Изменить: ${changed.join(", ")}` : null,
    archived.length ? `Убрать из прайса: ${archived.join(", ")}` : null,
    restored.length ? `Вернуть в прайс: ${restored.join(", ")}` : null,
  ].filter(Boolean).join("\n") || "Изменений нет.";
}

async function saveServiceCatalog() {
  document.querySelectorAll("[data-service-field]").forEach((control) => control.dispatchEvent(new Event("change")));
  const activeServices = serviceCatalogDraft.filter((service) => service.is_active).map(normalizeCatalogService);
  if (!activeServices.length) return window.alert("В прайсе должна остаться хотя бы одна позиция.");
  if (activeServices.some((service) => !service.public_name)) return window.alert("У каждой позиции должно быть название.");
  const summary = catalogDiffSummary(activeServices);
  if (summary === "Изменений нет.") return window.alert(summary);
  if (!window.confirm(`${summary}\n\nСохранить прайс?`)) return;
  const button = document.querySelector("#save-catalog");
  button.disabled = true;
  button.textContent = "Сохраняем…";
  try {
    const result = await api("/web/api/services/catalog", {
      method: "PUT",
      body: JSON.stringify({ services: activeServices }),
    });
    if (result.verified !== true) throw new Error("unverified_catalog");
    await renderServices("Прайс сохранён и проверен.");
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    window.alert("Не удалось сохранить прайс. Проверьте поля и попробуйте ещё раз.");
    button.disabled = false;
    button.textContent = "Проверить и сохранить";
  }
}

async function renderServices(message = "") {
  appShell("Мой прайс", `<div class="loading-state">Загружаем прайс…</div>`);
  try {
    const data = await api("/web/api/services");
    serviceCatalogOriginal = cloneCatalog(data.services);
    serviceCatalogDraft = cloneCatalog(data.services.filter((service) => service.is_active));
    expandedServiceIndex = null;
    removedCatalogExpanded = false;
    renderServiceCatalogBody(message);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    document.querySelector("#page-content").innerHTML = `<div class="panel error-state"><strong>Не удалось загрузить прайс</strong><button id="retry-services" class="secondary-button">Повторить</button></div>`;
    document.querySelector("#retry-services").addEventListener("click", () => renderServices());
  }
}

const originalCatalogAppShell = appShell;
appShell = function catalogAppShell(title, body) {
  originalCatalogAppShell(title, body);
  const nav = document.querySelector(".nav");
  if (!nav || nav.querySelector('[data-view="services"]')) return;
  const button = document.createElement("button");
  button.className = `tab-button ${state.view === "services" ? "active" : ""}`;
  button.dataset.view = "services";
  button.textContent = "Мой прайс";
  button.addEventListener("click", () => {
    state.view = "services";
    renderApp();
  });
  nav.append(button);
};

const originalCatalogRenderApp = renderApp;
renderApp = async function catalogRenderApp() {
  if (state.view !== "services") return originalCatalogRenderApp();
  clearPoll();
  try {
    await api("/web/api/auth/session");
  } catch (error) {
    if (error.status === 401) return renderLogin();
    return renderLogin("Не удалось проверить сессию.");
  }
  return renderServices();
};
