longAbsentInsightText = function longAbsentInsightTextWithCorrectPlural(clients) {
  if (!clients.length) return "";
  const count = clients.length;
  const lastTwo = count % 100;
  const last = count % 10;
  let phrase = "клиенток давно не было";
  if (lastTwo < 11 || lastTwo > 14) {
    if (last === 1) phrase = "клиентка давно не была";
    else if (last >= 2 && last <= 4) phrase = "клиентки давно не были";
  }
  return `${count} ${phrase} — посмотреть`;
};
