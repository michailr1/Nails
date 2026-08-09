function catalogMoney(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  const formatted = Number.isInteger(number)
    ? number.toLocaleString("ru-RU")
    : number.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return formatted;
}

catalogPriceSummary = function readableCatalogPriceSummary(service) {
  const currency = service.currency === "RUB" || !service.currency ? " ₽" : ` ${service.currency}`;
  if (service.price_type === "range") {
    const low = catalogMoney(service.price_min_amount);
    const high = catalogMoney(service.price_max_amount);
    return low && high ? `${low}–${high}${currency}` : "цена уточняется";
  }
  if (service.price_type === "per_unit") {
    const amount = catalogMoney(service.price_amount);
    const unit = String(service.price_unit || "ед.").trim();
    return amount ? `${amount}${currency} / ${escapeHtml(unit)}` : "цена уточняется";
  }
  if (service.price_type === "on_request") return "цена уточняется";
  const amount = catalogMoney(service.price_amount);
  return amount ? `${amount}${currency}` : "цена уточняется";
};

function catalogDuration(minutes, { approximate = false, addon = false } = {}) {
  const total = Number(minutes || 0);
  if (!total) return addon ? "без доп. времени" : "время не указано";
  const hours = Math.floor(total / 60);
  const remainder = total % 60;
  const prefix = approximate ? "~" : addon ? "+" : "";
  if (hours && remainder) return `${prefix}${hours} ч ${remainder} мин`;
  if (hours) return `${prefix}${hours} ч`;
  return `${prefix}${remainder} мин`;
}

catalogTimeSummary = function readableCatalogTimeSummary(service) {
  if (service.kind === "addon") {
    return catalogDuration(service.extra_minutes, { addon: true });
  }
  const duration = catalogDuration(service.duration_minutes, { approximate: true });
  const bufferAfter = Number(service.buffer_after_minutes || 0);
  return bufferAfter ? `${duration} · +${bufferAfter} мин после` : duration;
};

function catalogPositionLabel(count) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} позиция`;
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return `${count} позиции`;
  return `${count} позиций`;
}

renderCatalogList = function renderCollapsibleCatalogList() {
  if (!serviceCatalogDraft.length) return '<div class="panel empty">В прайсе пока нет позиций.</div>';
  return catalogGroups().map(([category, items]) => {
    const hasEditingCard = items.some(({ index }) => index === expandedServiceIndex);
    return `<details class="panel catalog-section catalog-section-collapsible" ${hasEditingCard ? "open" : ""}>
      <summary class="catalog-section-summary">
        <span><strong>${escapeHtml(category)}</strong><small>${escapeHtml(catalogPositionLabel(items.length))}</small></span>
        <span class="catalog-section-toggle" aria-hidden="true"></span>
      </summary>
      <div class="catalog-section-list">${items.map(({ service, index }) => (
        index === expandedServiceIndex ? serviceEditorCard(service, index) : serviceSummaryCard(service, index)
      )).join("")}</div>
    </details>`;
  }).join("");
};
