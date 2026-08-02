const CABINET_VIEWS = new Set(["calendar", "clients", "services", "statistics"]);
const CABINET_ROUTE_PARAM = "section";

function cabinetViewFromLocation() {
  const url = new URL(window.location.href);
  const requested = url.searchParams.get(CABINET_ROUTE_PARAM);
  return CABINET_VIEWS.has(requested) ? requested : "calendar";
}

function cabinetUrlForView(view) {
  const url = new URL(window.location.href);
  if (view === "calendar") url.searchParams.delete(CABINET_ROUTE_PARAM);
  else url.searchParams.set(CABINET_ROUTE_PARAM, view);
  return `${url.pathname}${url.search}${url.hash}`;
}

function cabinetWriteRoute(view, { replace = false } = {}) {
  if (!CABINET_VIEWS.has(view)) return;
  const method = replace ? "replaceState" : "pushState";
  window.history[method]({ cabinetView: view }, "", cabinetUrlForView(view));
}

function cabinetRestoreView() {
  const requested = cabinetViewFromLocation();
  if (state.view === requested) return;
  state.view = requested;
  renderApp();
}

document.addEventListener("click", (event) => {
  const logoutButton = event.target.closest(".logout-button");
  if (logoutButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const confirmed = window.confirm(
      "Выйти из кабинета? Для повторного входа потребуется подтверждение в Telegram.",
    );
    if (confirmed) logout();
    return;
  }

  const viewButton = event.target.closest("[data-view]");
  if (!viewButton || !CABINET_VIEWS.has(viewButton.dataset.view)) return;
  if (cabinetViewFromLocation() !== viewButton.dataset.view) {
    cabinetWriteRoute(viewButton.dataset.view);
  }
}, true);

window.addEventListener("popstate", cabinetRestoreView);

const initialCabinetView = cabinetViewFromLocation();
const initialCabinetViewChanged = state.view !== initialCabinetView;
state.view = initialCabinetView;
cabinetWriteRoute(initialCabinetView, { replace: true });
if (initialCabinetViewChanged) renderApp();
