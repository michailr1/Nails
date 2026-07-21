function bookingDisplayPrice(booking) {
  if (booking.price_amount === null || booking.price_amount === undefined || booking.price_amount === "") {
    return "Цена после уточнения";
  }
  const formatted = formatMoney(booking.price_amount, booking.currency);
  if (booking.price_confirmed || booking.price_type === "fixed") return formatted;
  return `от ${formatted}`;
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
    <div><h3>${escapeHtml(booking.client_name)}</h3><p>${escapeHtml(booking.service_name)} · до ${escapeHtml(format.format(end))}</p><span class="badge">${escapeHtml(booking.status)}</span></div>
    <div class="price">${escapeHtml(bookingDisplayPrice(booking))}</div>
  </article>`;
};
