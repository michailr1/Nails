function revenueBarRows(items) {
  const valuedItems = items.filter((item) => Number(item.revenue_amount) > 0);
  if (!valuedItems.length) {
    return '<p class="muted statistics-empty">Пока нет записей с ценой, которую можно распределить по позициям.</p>';
  }
  const max = Math.max(...valuedItems.map((item) => Number(item.revenue_amount)), 1);
  return `<div class="statistics-bars">${valuedItems.slice(0, 6).map((item) => `
    <div class="statistics-bar-row">
      <div class="statistics-bar-label"><span>${escapeHtml(item.name)}</span><strong>${escapeHtml(formatMoney(item.revenue_amount))}</strong></div>
      <div class="statistics-bar-track" aria-hidden="true"><span style="width:${Math.max(8, Math.round((Number(item.revenue_amount) / max) * 100))}%"></span></div>
    </div>`).join("")}</div>`;
}

barRows = function barRowsByRevenue(items) {
  return revenueBarRows(items);
};

const renderStatisticsWithoutRevenueCopy = renderStatistics;
renderStatistics = async function renderStatisticsWithRevenueCopy() {
  await renderStatisticsWithoutRevenueCopy();
  if (state.view !== "statistics") return;
  document.querySelectorAll(".statistics-panel .statistics-section-title").forEach((title) => {
    const heading = title.querySelector("h2");
    const label = title.querySelector("span");
    if (!heading || !label || !["Процедуры", "Дополнения"].includes(heading.textContent)) return;
    label.textContent = "Вклад в выручку";
    const panel = title.closest(".statistics-panel");
    if (!panel || panel.querySelector(".statistics-revenue-note")) return;
    const note = document.createElement("p");
    note.className = "muted statistics-revenue-note";
    note.textContent = "Только записи, где цену можно честно распределить по составу.";
    title.after(note);
  });
};
