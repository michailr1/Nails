const stableRenderCalendar = renderCalendar;
renderCalendar = async function renderCalendarWithViewGuard() {
  const requestedView = state.view;
  await stableRenderCalendar();
  if (requestedView === "calendar" && state.view !== "calendar") {
    return renderApp();
  }
};

const stableRenderStatistics = renderStatistics;
renderStatistics = async function renderStatisticsWithViewGuard() {
  const requestedView = state.view;
  await stableRenderStatistics();
  if (requestedView === "statistics" && state.view !== "statistics") {
    return renderApp();
  }
};

function clarifyTelegramInvite(root = document) {
  root.querySelectorAll?.("#show-client-invitation").forEach((button) => {
    button.textContent = "Пригласить клиентку в Telegram";
    button.setAttribute(
      "aria-label",
      "Получить общую ссылку, чтобы пригласить клиентку в Telegram",
    );
  });

  root.querySelectorAll?.(".client-invite-block p").forEach((title) => {
    if (title.textContent.trim() === "Общая ссылка для записи") {
      title.textContent = "Приглашение клиентки в Telegram";
    }
  });
}

const viewStabilityObserver = new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (!(node instanceof Element)) continue;
      clarifyTelegramInvite(node);
    }
  }
});

viewStabilityObserver.observe(document.documentElement, {
  childList: true,
  subtree: true,
});
clarifyTelegramInvite();
