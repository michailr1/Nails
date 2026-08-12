const WEB_AUTH_OPEN_STATUSES = new Set(["pending"]);

pollChallenge = async function pollChallenge() {
  if (!state.challenge) return;
  try {
    const current = await api(`/web/api/auth/challenges/${encodeURIComponent(state.challenge.challenge_id)}`);
    if (current.status === "approved") {
      renderConfirmation("Подтверждение получено. Открываем кабинет…");
      const result = await api("/web/api/auth/challenges/consume", {
        method: "POST",
        body: JSON.stringify({ challenge_id: state.challenge.challenge_id }),
      });
      if (result.authenticated) {
        state.challenge = null;
        clearPoll();
        return renderApp();
      }
      return renderLogin("Не удалось завершить подтверждённый вход. Начните вход заново.");
    }

    if (WEB_AUTH_OPEN_STATUSES.has(current.status)) {
      state.pollTimer = window.setTimeout(pollChallenge, 1800);
      return;
    }

    const messages = {
      expired: "Время подтверждения истекло.",
      locked: "Запрос заблокирован после нескольких попыток.",
      denied: "Вход отклонён в Telegram.",
      consumed: "Этот запрос уже использован. Если кабинет не открылся, начните вход заново.",
    };
    return renderLogin(
      messages[current.status]
        || "Запрос на вход завершён в неизвестном состоянии. Начните вход заново.",
    );
  } catch (error) {
    if (error.status === 404) return renderLogin("Запрос больше не действует. Начните вход заново.");
    state.pollTimer = window.setTimeout(pollChallenge, 3000);
  }
};

function handoffContinuationToken() {
  const fragment = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  return new URLSearchParams(fragment).get("continue") || "";
}

function handoffContinuationUrl() {
  const token = handoffContinuationToken();
  if (!token) return "";
  return `/web/api/auth/continue?token=${encodeURIComponent(token)}`;
}

function ensureBrowserHandoff() {
  const href = handoffContinuationUrl();
  if (!href) return;
  let link = document.querySelector("#open-in-browser-handoff");
  if (!link) {
    link = document.createElement("a");
    link.id = "open-in-browser-handoff";
    link.className = "secondary-button";
    link.textContent = "Открыть в браузере";
    link.target = "_blank";
    link.rel = "noopener noreferrer external";
  }
  link.href = href;

  const actions = document.querySelector("#page-actions");
  if (actions) {
    if (link.parentElement !== actions) actions.prepend(link);
    return;
  }

  const authCard = document.querySelector(".auth-card");
  if (authCard && link.parentElement !== authCard) authCard.append(link);
}

const handoffObserver = new MutationObserver(ensureBrowserHandoff);
handoffObserver.observe(document.querySelector("#app"), { childList: true, subtree: true });
ensureBrowserHandoff();
