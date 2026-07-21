function bookingDisplayPrice(booking) {
  const hasExactPrice = booking.price_amount !== null
    && booking.price_amount !== undefined
    && booking.price_amount !== "";
  if (hasExactPrice) {
    const formatted = formatMoney(booking.price_amount, booking.currency);
    if (booking.price_confirmed || booking.price_type === "fixed") return formatted;
    return `от ${formatted}`;
  }

  const hasMinimum = booking.price_min_amount !== null
    && booking.price_min_amount !== undefined
    && booking.price_min_amount !== "";
  if (hasMinimum) return `от ${formatMoney(booking.price_min_amount, booking.currency)}`;
  return "Цена после уточнения";
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
