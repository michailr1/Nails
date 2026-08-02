const PERSONAL_LINK_BLOCK_SELECTOR = ".client-personal-invite-block";

function personalLinkHelpText() {
  return "Отправьте эту ссылку клиентке. После перехода она подключится к вашему Telegram-боту и сможет пользоваться записью.";
}

function enhancePersonalLinkControl(actions) {
  if (!actions || actions.dataset.personalLinkEnhanced === "true") return;
  const title = actions.querySelector(".client-personal-link-title");
  const help = actions.querySelector(".client-personal-link-help");
  const button = actions.querySelector("[data-personal-invite]");
  if (!title || !help || !button) return;

  actions.dataset.personalLinkEnhanced = "true";
  title.textContent = "Подключить клиентку к Telegram";
  help.textContent = personalLinkHelpText();
  button.textContent = "Получить ссылку";
  button.setAttribute("aria-expanded", "false");
}

function enhancePersonalLinkControls(root = document) {
  root.querySelectorAll?.(".client-reachability-actions").forEach(enhancePersonalLinkControl);
}

function closePersonalLink(actions) {
  actions.querySelector(PERSONAL_LINK_BLOCK_SELECTOR)?.remove();
  const trigger = actions.querySelector("[data-personal-invite]");
  if (trigger) {
    trigger.textContent = "Получить ссылку";
    trigger.setAttribute("aria-expanded", "false");
  }
}

function renderPersonalLink(actions, url) {
  actions.querySelector(PERSONAL_LINK_BLOCK_SELECTOR)?.remove();
  const block = document.createElement("div");
  block.className = "client-invite-block client-personal-invite-block";
  block.innerHTML = `
    <div class="client-personal-invite-heading">
      <div>
        <p>Ссылка для этой клиентки</p>
        <small class="muted">После перехода клиентка подключится к вашему Telegram-боту.</small>
      </div>
      <button class="client-personal-close" type="button" data-close-personal-link aria-label="Скрыть ссылку">Скрыть</button>
    </div>
    <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>
    <div class="client-invite-actions">
      <button class="secondary-button" type="button" data-copy-personal-link>Скопировать</button>
      <span class="muted small" data-copy-status aria-live="polite"></span>
    </div>`;

  block.querySelector("[data-copy-personal-link]")?.addEventListener("click", async () => {
    await copyText(url, block.querySelector("[data-copy-status]"));
  });
  block.querySelector("[data-close-personal-link]")?.addEventListener("click", () => {
    closePersonalLink(actions);
  });
  actions.append(block);

  const trigger = actions.querySelector("[data-personal-invite]");
  if (trigger) {
    trigger.textContent = "Скрыть";
    trigger.setAttribute("aria-expanded", "true");
  }
}

async function togglePersonalLink(button) {
  const actions = button.closest(".client-reachability-actions");
  if (!actions) return;
  if (actions.querySelector(PERSONAL_LINK_BLOCK_SELECTOR)) {
    closePersonalLink(actions);
    return;
  }

  button.disabled = true;
  actions.querySelector(".client-invite-error")?.remove();
  try {
    let url = button.dataset.personalInviteUrl;
    if (!url) {
      const payload = await api(`/web/api/client-linking/clients/${encodeURIComponent(button.dataset.personalInvite)}/personal-link`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      url = payload.invitation_url || "";
      button.dataset.personalInviteUrl = url;
    }
    if (!url) throw new Error("personal_link_missing");
    renderPersonalLink(actions, url);
    await copyText(url, actions.querySelector("[data-copy-status]"));
  } catch (error) {
    if (error.status === 401) return renderLogin("Сессия завершилась. Войдите снова.");
    const line = document.createElement("span");
    line.className = "client-invite-error small";
    line.textContent = typeof clientLinkErrorText === "function"
      ? clientLinkErrorText(error)
      : "Не удалось подготовить ссылку.";
    actions.append(line);
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-personal-invite]");
  if (!button) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  togglePersonalLink(button);
}, true);

const personalLinkObserver = new MutationObserver((records) => {
  records.forEach((record) => {
    record.addedNodes.forEach((node) => {
      if (!(node instanceof Element)) return;
      if (node.matches(".client-reachability-actions")) enhancePersonalLinkControl(node);
      enhancePersonalLinkControls(node);
    });
  });
});

personalLinkObserver.observe(document.documentElement, { childList: true, subtree: true });
enhancePersonalLinkControls();
