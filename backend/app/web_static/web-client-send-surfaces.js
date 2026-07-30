function clientMessagingUnavailableButton(label, extraClass = "") {
  return `<button class="secondary-button ${extraClass}" type="button" disabled title="Отправка станет доступна после контролируемого запуска клиентского бота">${escapeHtml(label)}</button>`;
}

const renderServicesWithoutClientMessagingSurface = renderServices;
renderServices = async function renderServicesWithClientMessagingSurface(message = "") {
  await renderServicesWithoutClientMessagingSurface(message);
  if (state.view !== "services") return;
  const actions = document.querySelector("#page-actions");
  if (!actions || actions.querySelector("[data-client-price-share]")) return;
  const wrapper = document.createElement("span");
  wrapper.dataset.clientPriceShare = "true";
  wrapper.innerHTML = clientMessagingUnavailableButton("Показать клиенткам");
  actions.prepend(wrapper);
};

const renderStatisticsWithoutClientMessagingSurface = renderStatistics;
renderStatistics = async function renderStatisticsWithClientMessagingSurface() {
  await renderStatisticsWithoutClientMessagingSurface();
  if (state.view !== "statistics") return;
  document.querySelectorAll("[data-long-absent-client-id]").forEach((row) => {
    const actions = row.querySelector(".long-absent-actions");
    if (!actions || actions.querySelector("[data-client-remind]")) return;
    const wrapper = document.createElement("span");
    wrapper.dataset.clientRemind = row.dataset.longAbsentClientId;
    wrapper.innerHTML = clientMessagingUnavailableButton("Напомнить");
    actions.prepend(wrapper);
  });
};

const webClientRenderContentWithoutMessagingSurface = webClientRenderContent;
webClientRenderContent = function webClientRenderContentWithMessagingSurface() {
  webClientRenderContentWithoutMessagingSurface();
  const editor = document.querySelector("#client-card-editor");
  if (!editor || editor.querySelector("[data-client-write]")) return;
  const actions = editor.querySelector(".client-card-actions");
  if (!actions) return;
  const clientId = editor.querySelector("#client-card-form")?.dataset.clientId || "";
  const wrapper = document.createElement("span");
  wrapper.dataset.clientWrite = clientId;
  wrapper.innerHTML = clientMessagingUnavailableButton("Написать");
  actions.prepend(wrapper);
};
