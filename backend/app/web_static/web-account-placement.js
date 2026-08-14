function masterAccountHostInTitleRow() {
  const topbar = document.querySelector(".topbar");
  if (!topbar) return null;

  let row = topbar.querySelector(".master-title-account-row");
  if (!row) {
    const title = topbar.firstElementChild;
    if (!title) return null;
    row = document.createElement("div");
    row.className = "master-title-account-row";
    topbar.insertBefore(row, title);
    row.append(title);
  }

  let host = row.querySelector(".master-account-host");
  if (!host) {
    host = topbar.querySelector(".master-account-host");
    if (host) row.append(host);
  }
  if (!host) {
    host = document.createElement("div");
    host.className = "master-account-host";
    row.append(host);
  }
  return host;
}

masterAccountHost = masterAccountHostInTitleRow;

const installMasterSettingsButtonBeforePlacement = installMasterSettingsButton;
installMasterSettingsButton = function installMasterSettingsButtonInTitleRow() {
  const existingHost = document.querySelector(".topbar > .master-account-host");
  if (existingHost) masterAccountHostInTitleRow();
  installMasterSettingsButtonBeforePlacement();
};
