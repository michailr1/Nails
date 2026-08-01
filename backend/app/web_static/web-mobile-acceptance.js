function bookingTimeSelectMarkup(name, selected = "11:00") {
  const values = [];
  for (let minutes = 0; minutes < 24 * 60; minutes += 15) {
    const hours = String(Math.floor(minutes / 60)).padStart(2, "0");
    const mins = String(minutes % 60).padStart(2, "0");
    const value = `${hours}:${mins}`;
    values.push(`<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`);
  }
  return `<select name="${name}" required>${values.join("")}</select>`;
}

const renderBookingComposerWithNativeTime = renderBookingComposer;
renderBookingComposer = function renderBookingComposerWithLightTimeSelect() {
  renderBookingComposerWithNativeTime();
  const input = document.querySelector('#booking-create-form input[name="time"]');
  if (!input) return;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = bookingTimeSelectMarkup("time", input.value || "11:00");
  input.replaceWith(wrapper.firstElementChild);
};

let mobileNavigationResizeObserver = null;

function syncMobileNavigationInset() {
  const sidebar = document.querySelector(".sidebar");
  const shell = document.querySelector(".app-shell");
  mobileNavigationResizeObserver?.disconnect();
  mobileNavigationResizeObserver = null;
  if (!sidebar || !shell) return;

  const update = () => {
    const height = Math.ceil(sidebar.getBoundingClientRect().height);
    shell.style.setProperty("--mobile-nav-height", `${height}px`);
  };
  update();
  mobileNavigationResizeObserver = new ResizeObserver(update);
  mobileNavigationResizeObserver.observe(sidebar);
}

const appShellWithoutMeasuredMobileNavigation = appShell;
appShell = function appShellWithMeasuredMobileNavigation(title, body) {
  appShellWithoutMeasuredMobileNavigation(title, body);
  syncMobileNavigationInset();
};
