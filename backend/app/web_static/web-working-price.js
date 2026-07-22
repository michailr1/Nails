function bookingWorkingPrice(services) {
  let minimum = 0;
  let maximum = 0;
  let estimated = false;
  let hasKnownPrice = false;

  services.filter(Boolean).forEach((service) => {
    if (service.price_type === "fixed") {
      const amount = Number(service.price_amount || 0);
      minimum += amount;
      maximum += amount;
      hasKnownPrice = true;
    } else if (service.price_type === "range") {
      minimum += Number(service.price_min_amount || 0);
      maximum += Number(service.price_max_amount || service.price_min_amount || 0);
      estimated = true;
      hasKnownPrice = true;
    } else if (service.price_type === "per_unit") {
      const amount = Number(service.price_amount || 0);
      minimum += amount;
      maximum += amount;
      estimated = true;
      hasKnownPrice = true;
    } else {
      estimated = true;
    }
  });

  return { minimum, maximum, estimated, hasKnownPrice };
}

bookingServicePrice = function workingServicePrice(service) {
  const money = (value) => `${Number(value || 0).toLocaleString("ru-RU")} ₽`;
  if (service.price_type === "range") return `от ${money(service.price_min_amount)}`;
  if (service.price_type === "per_unit") return `от ${money(service.price_amount)}`;
  if (service.price_type === "on_request") return "индивидуальная цена";
  return money(service.price_amount);
};

bookingEstimatedPrice = function workingEstimatedPrice(services, overrideValue = "") {
  if (overrideValue !== "") return `${Number(overrideValue).toLocaleString("ru-RU")} ₽ — указано для этой записи`;
  if (!services.length) return "Выберите процедуру";
  const price = bookingWorkingPrice(services);
  if (!price.hasKnownPrice) return "Индивидуальная цена";
  return `${price.estimated ? "от " : ""}${price.minimum.toLocaleString("ru-RU")} ₽`;
};

const bookingPayloadWithoutWorkingPrice = bookingPayload;
bookingPayload = function bookingPayloadWithWorkingPrice(form) {
  const payload = bookingPayloadWithoutWorkingPrice(form);
  if (payload.body.price_override_amount !== null) return payload;
  const price = bookingWorkingPrice([payload.base, ...payload.addons]);
  if (price.hasKnownPrice) payload.body.price_override_amount = price.minimum;
  return payload;
};
