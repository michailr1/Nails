let serviceCatalogDraft = [];
let serviceCatalogOriginal = [];

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
    public_name: "Новая услуга",
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

function servicePriceFields(service, index) {
  if (service.price_type === "range") {
    return `${catalogField(service, index, "price_min_amount", "Цена от, ₽", "number", "Нижняя граница стоимости.")}${catalogField(service, index, "price_max_amount", "Цена до, ₽", "number", "Верхняя граница стоимости.")}`;
  }
  if (service.price_type === "per_unit") {
    return `${catalogField(service, index, "price_amount", "Цена, ₽", "number", "Стоимость одной единицы.")}${catalogField(service, index, "price_unit", "За что цена", "text", "Например: за ноготь или за минуту.")}`;
  }
  if (service.price_type === "fixed") {
    return catalogField(service, index, "price_amount", "Цена, ₽", "number", "Полная стоимость услуги.");
  }
  return "";
}

function serviceEditorCard(service, index) {
  const timeFields = service.kind === "addon"
    ? catalogField(service, index, "extra_minutes", "Доп. время, мин", "number", "Насколько дополнение увеличивает запись.", true)
    : `${catalogField(service, index, "duration_minutes", "Длительность, мин", "number", "Сколько обычно занимает услуга.")}${catalogField(service, index, "buffer_before_minutes", "Резерв до, мин", "number", "Свободное время перед записью.", true)}${catalogField(service, index, "buffer_after_minutes", "Резерв после, мин", "number", "Свободное время после записи.", true)}`;
  return `<article class="panel catalog-card ${service.is_active ? "" : "catalog-archived"}">
    <div class="panel-header">
      <strong>${escapeHtml(service.public_name || "Новая услуга")}</strong>
      <label class="catalog-active"><input data-service-index="${index}" data-service-field="is_active" type="checkbox" ${service.is_active ? "checked" : ""}> Активна</label>
    </div>
    <div class="catalog-grid">
      ${catalogField(service, index, "public_name", "Название", "text", "Так услуга будет показана в кабинете и записях.")}
      ${catalogField(service, index, "public_description", "Описание", "text", "Короткое пояснение для мастера.", true)}
      ${catalogSelect(service, index, "kind", "Тип услуги", [["base", "Основная"], ["addon", "Дополнение"]], "Дополнение добавляется к основной услуге.")}
      ${catalogSelect(service, index, "price_type", "Как указана цена", [["fixed", "Фиксированная"], ["range", "Диапазон"], ["per_unit", "За единицу"], ["on_request", "По запросу"]], "Поля цены появятся только когда они нужны.")}
      ${servicePriceFields(service, index)}
      ${timeFields}
      ${catalogField(service, index, "category", "Категория", "text", "Помогает группировать услуги, например «Маникюр».", true)}
    </div>
  </article>`;
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
    <div class="info-note">Обязательны только основные данные, нужные для выбранного типа услуги и цены. Поля с пометкой «необязательно» можно оставить пустыми. Сохранение применяется ко всему активному каталогу одной операцией.</div>
    <div class="catalog-actions"><button id="add-service" class="secondary-button" type="button">Добавить услугу</button><button id="save-catalog" class="primary-button" type="button">Проверить и сохранить</button></div>
    <div class="catalog-list">${serviceCatalogDraft.map(serviceEditorCard).join("")}</div>`;
  document.querySelector("#add-service").addEventListener("click", () => {
    serviceCatalogDraft.push(emptyCatalogService());
    renderServiceCatalogBody();
  });
  document.querySelector("#save-catalog").addEventListener("click", saveServiceCatalog);
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
    return original && JSON.stringify(normalizeCatalogService(original)) !== JSON.stringify(item);
  }).map((item) => item.public_name);
  const archived = serviceCatalogOriginal.filter((item) => item.is_active && !futureNames.has(item.public_name)).map((item) => item.public_name);
  return [
    created.length ? `Добавить: ${created.join(", ")}` : null,
    changed.length ? `Изменить: ${changed.join(", ")}` : null,
    archived.length ? `Архивировать: ${archived.join(", ")}` : null,
  ].filter(Boolean).join("\n") || "Изменений нет.";
}

async function saveServiceCatalog() {
  document.querySelectorAll("[data-service-field]").forEach((control) => control.dispatchEvent(new Event("change")));
  const activeServices = serviceCatalogDraft.filter((service) => service.is_active).map(normalizeCatalogService);
  if (!activeServices.length) return window.alert("В каталоге должна остаться хотя бы одна активная услуга.");
  if (activeServices.some((service) => !service.public_name)) return window.alert("У каждой услуги должно быть название.");
  const summary = catalogDiffSummary(activeServices);
  if (summary === "Изменений нет.") return window.alert(summary);
  if (!window.confirm(`${summary}\n\nСохранить весь каталог?`)) return;
  const button = document.querySelector("#save-catalog");
  button.disabled = true;
  button.textContent = "Сохраняем…";
  try {
    const result = await api("/web/api/services/catalog", {
      method: "PUT",
      body: JSON.stringify({ services: activeServices }),
    });
    if (result.verified !== true) throw new Error("unverified_catalog");
    await renderServices("Каталог сохранён и проверен.");
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    window.alert("Не удалось сохранить каталог. Проверьте поля и попробуйте ещё раз.");
    button.disabled = false;
    button.textContent = "Проверить и сохранить";
  }
}

async function renderServices(message = "") {
  appShell("Услуги", `<div class="loading-state">Загружаем каталог…</div>`);
  try {
    const data = await api("/web/api/services");
    serviceCatalogOriginal = cloneCatalog(data.services);
    serviceCatalogDraft = cloneCatalog(data.services);
    renderServiceCatalogBody(message);
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    document.querySelector("#page-content").innerHTML = `<div class="panel error-state"><strong>Не удалось загрузить услуги</strong><button id="retry-services" class="secondary-button">Повторить</button></div>`;
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
  button.textContent = "Услуги";
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
