let calendarServicePriceIndex = new Map();

function calendarMoney(amount, currency = "RUB") {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: currency || "RUB",
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

function bookingCatalogPrice(booking) {
  const names = String(booking.service_name || "")
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
  if (!names.length) return null;

  let total = 0;
  let isMinimum = false;
  for (const name of names) {
    const service = calendarServicePriceIndex.get(name);
    if (!service) return null;
    if (service.price_type === "fixed") {
      if (service.price_amount === null || service.price_amount === undefined || service.price_amount === "") return null;
      total += Number(service.price_amount);
      continue;
    }
    if (service.price_type === "range") {
      if (service.price_min_amount === null || service.price_min_amount === undefined || service.price_min_amount === "") return null;
      total += Number(service.price_min_amount);
      isMinimum = true;
      continue;
    }
    return null;
  }

  const currency = calendarServicePriceIndex.get(names[0])?.currency || booking.currency || "RUB";
  return isMinimum ? `от ${calendarMoney(total, currency)}` : calendarMoney(total, currency);
}

const apiWithoutCalendarPriceFallback = api;
api = async function apiWithCalendarPriceFallback(path, options = {}) {
  const payload = await apiWithoutCalendarPriceFallback(path, options);
  if (String(path).startsWith("/web/api/calendar?")) {
    try {
      const catalog = await apiWithoutCalendarPriceFallback("/web/api/services");
      calendarServicePriceIndex = new Map(
        (catalog.services || []).map((service) => [String(service.public_name || "").trim(), service]),
      );
    } catch {
      calendarServicePriceIndex = new Map();
    }
  }
  return payload;
};

function bookingDisplayPrice(booking) {
  const hasExactPrice = booking.price_amount !== null
    && booking.price_amount !== undefined
    && booking.price_amount !== "";
  if (hasExactPrice) {
    const formatted = calendarMoney(booking.price_amount, booking.currency);
    if (booking.price_confirmed || booking.price_type === "fixed") return formatted;
    return `от ${formatted}`;
  }

  const hasMinimum = booking.price_min_amount !== null
    && booking.price_min_amount !== undefined
    && booking.price_min_amount !== "";
  if (hasMinimum) return `от ${calendarMoney(booking.price_min_amount, booking.currency)}`;

  return bookingCatalogPrice(booking) || "Цена после уточнения";
}

function bookingStatusBadge(status) {
  if (status === "cancelled") return '<span class="badge">Отменена</span>';
  if (status === "no_show") return '<span class="badge">Не пришла</span>';
  return "";
}

bookingCard = function bookingCardWithKnownPrice(booking, timezone) {
  const start = new Date(booking.starts_at);
  const end = new Date(booking.ends_at);
  const format = new Intl.DateTimeFormat("ru-RU", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
  });
  return `<article class="booking">
    <div class="time">${escapeHtml(format.format(start))}</div>
    <div><h3>${escapeHtml(booking.client_name)}</h3><p>${escapeHtml(booking.service_name)} · до ${escapeHtml(format.format(end))}</p>${bookingStatusBadge(booking.status)}</div>
    <div class="price">${escapeHtml(bookingDisplayPrice(booking))}</div>
  </article>`;
};
