const bookingCardWithoutWorkingPrice = bookingCard;

function bookingDisplayPrice(booking) {
  if (booking.price_amount === null || booking.price_amount === undefined || booking.price_amount === "") {
    return "Индивидуальная цена";
  }
  const amount = formatMoney(booking.price_amount, booking.currency);
  const estimated = booking.price_type === "range" || booking.price_type === "per_unit" || !booking.price_confirmed;
  return estimated ? `от ${amount}` : amount;
}

bookingCard = function bookingCardWithWorkingPrice(booking, timezone) {
  const card = bookingCardWithoutWorkingPrice(booking, timezone);
  return card.replace(
    /<div class="price">.*?<\/div>/,
    `<div class="price">${escapeHtml(bookingDisplayPrice(booking))}</div>`,
  );
};
