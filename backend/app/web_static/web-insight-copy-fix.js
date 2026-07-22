longAbsentInsightText = function longAbsentInsightHumanText(clients) {
  const count = clients.length;
  if (!count) return "";
  if (count === 1) return "Давно не была 1 клиентка";
  if (count >= 2 && count <= 4) return `Давно не были ${count} клиентки`;
  return `Давно не были ${count} клиенток`;
};

const addLongAbsentCalendarInsightWithoutCopyFix = addLongAbsentCalendarInsight;
addLongAbsentCalendarInsight = async function addLongAbsentCalendarInsightWithHumanCopy() {
  await addLongAbsentCalendarInsightWithoutCopyFix();
  const insight = document.querySelector(".naily-insight");
  if (!insight) return;
  const label = insight.querySelector(".naily-insight-label");
  if (label) label.textContent = "Нэйли подсказывает";
};
