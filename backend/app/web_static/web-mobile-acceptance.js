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
