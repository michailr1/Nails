const TELEGRAM_BOT_USERNAME = "smartnails_bot";
const LOGIN_CHALLENGE_STORAGE_KEY = "nails.web-login.pending-challenge";
const CHALLENGE_POLL_INTERVAL_MS = 4500;
const CONSUME_RETRY_INTERVAL_MS = 5000;
const MAX_CONSUME_RATE_LIMIT_RETRIES = 3;
let challengeRestoreInFlight = false;
let challengePollInFlight = false;
let consumeRateLimitRetries = 0;
let appRenderWrapped = false;

const replacements = new Map([
  ["Мы покажем число для сверки и отправим запрос в закрытый бот. В Telegram достаточно нажать «Подтвердить».", "Мы покажем шестизначное число. Отправьте его Нэйли в закрытом Telegram-боте — это сразу подтвердит вход."],
  ["Войти через Telegram", "Получить число"],
  ["Код вводить на сайте или в Telegram не нужно.", "Число вводится только в переписке с Нэйли. На сайте его вводить не нужно."],
  ["Сверьте число", "Отправьте число Нэйли"],
  ["Подтвердите вход", "Подтвердите вход в Telegram"],
  ["В закрытом Telegram-боте появится запрос с тем же числом.", "Нажмите кнопку под числом. Telegram откроется отдельно и подставит готовое подтверждение. После отправки вернитесь на сайт — кабинет откроется автоматически."],
  ["Ожидаем подтверждение в Telegram…", "Ждём подтверждение в диалоге с Нэйли…"],
  ["Вход отклонён в Telegram.", "Вход отклонён в диалоге с Нэйли."],
]);

function applyWeb001eCopy(root = document) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const replacement = replacements.get(node.nodeValue.trim());
    if (replacement) node.nodeValue = replacement;
  }
}

function releaseInitialSessionCheck() {
  return window.__nailsWebAuthBootstrap?.releaseSessionCheck() === true;
}

function rememberCurrentChallenge() {
  if (typeof state === "undefined" || !state.challenge) return;
  const challengeId = state.challenge.challenge_id;
  const verificationNumber = state.challenge.verification_number;
  if (!challengeId || !/^\d{6}$/.test(String(verificationNumber))) return;
  localStorage.setItem(LOGIN_CHALLENGE_STORAGE_KEY, JSON.stringify({
    challenge_id: challengeId,
    verification_number: String(verificationNumber),
  }));
}

function forgetStoredChallenge() {
  localStorage.removeItem(LOGIN_CHALLENGE_STORAGE_KEY);
}

function readStoredChallenge() {
  try {
    const stored = JSON.parse(localStorage.getItem(LOGIN_CHALLENGE_STORAGE_KEY) || "null");
    if (!stored?.challenge_id || !/^\d{6}$/.test(String(stored.verification_number))) {
      forgetStoredChallenge();
      return null;
    }
    return stored;
  } catch {
    forgetStoredChallenge();
    return null;
  }
}

function addTelegramCodeButton(root = document) {
  const verificationNumber = root.querySelector?.(".verification-number") || document.querySelector(".verification-number");
  if (!verificationNumber || document.querySelector("#send-code-to-naily")) return;
  const code = verificationNumber.textContent.trim();
  if (!/^\d{6}$/.test(code)) return;
  rememberCurrentChallenge();
  const link = document.createElement("a");
  link.id = "send-code-to-naily";
  link.className = "primary-button telegram-code-button";
  link.href = `https://t.me/${TELEGRAM_BOT_USERNAME}?text=${encodeURIComponent(`Нэйли, подтверждаю вход: ${code}`)}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Отправить код Нэйли";
  verificationNumber.insertAdjacentElement("afterend", link);
}

function bindChallengeReset(root = document) {
  const button = root.querySelector?.("#cancel-login") || document.querySelector("#cancel-login");
  if (!button || button.dataset.challengeResetBound === "true") return;
  button.dataset.challengeResetBound = "true";
  button.addEventListener("click", () => {
    consumeRateLimitRetries = 0;
    forgetStoredChallenge();
    releaseInitialSessionCheck();
  }, { once: true });
}

function wrapAuthenticatedRender() {
  if (appRenderWrapped || typeof renderApp !== "function") return;
  const originalRenderApp = renderApp;
  renderApp = (...args) => {
    releaseInitialSessionCheck();
    return originalRenderApp(...args);
  };
  appRenderWrapped = true;
}

function finishAuthenticatedLogin() {
  consumeRateLimitRetries = 0;
  forgetStoredChallenge();
  state.challenge = null;
  clearPoll();
  const resumedInitialRender = releaseInitialSessionCheck();
  if (!resumedInitialRender) renderApp();
}

function failConsumeLogin() {
  consumeRateLimitRetries = 0;
  forgetStoredChallenge();
  state.challenge = null;
  clearPoll();
  releaseInitialSessionCheck();
  renderLogin("Не удалось открыть кабинет. Получите новое число и войдите заново.");
}

async function pollPersistedChallenge() {
  if (!state.challenge || challengePollInFlight) return;
  challengePollInFlight = true;
  let stage = "poll";
  try {
    const current = await api(`/web/api/auth/challenges/${encodeURIComponent(state.challenge.challenge_id)}`);
    if (current.status === "approved") {
      renderConfirmation("Подтверждение получено. Открываем кабинет…");
      stage = "consume";
      const result = await api("/web/api/auth/challenges/consume", {
        method: "POST",
        body: JSON.stringify({ challenge_id: state.challenge.challenge_id }),
      });
      consumeRateLimitRetries = 0;
      if (result.authenticated) return finishAuthenticatedLogin();
    }
    if (["expired", "locked", "denied", "consumed"].includes(current.status)) {
      forgetStoredChallenge();
      return renderLogin("Запрос больше не действует. Начните вход заново.");
    }
    state.pollTimer = window.setTimeout(pollChallenge, CHALLENGE_POLL_INTERVAL_MS);
  } catch (error) {
    if (error.status === 404) {
      forgetStoredChallenge();
      return renderLogin("Запрос больше не действует. Начните вход заново.");
    }
    if (stage === "consume" && [429, 503].includes(error.status)) {
      consumeRateLimitRetries += 1;
      if (consumeRateLimitRetries >= MAX_CONSUME_RATE_LIMIT_RETRIES) {
        return failConsumeLogin();
      }
      renderConfirmation("Сервер занят. Повторяем открытие кабинета…");
      state.pollTimer = window.setTimeout(pollChallenge, CONSUME_RETRY_INTERVAL_MS);
      return;
    }
    const retryDelay = [429, 503].includes(error.status)
      ? CHALLENGE_POLL_INTERVAL_MS
      : 5000;
    state.pollTimer = window.setTimeout(pollChallenge, retryDelay);
  } finally {
    challengePollInFlight = false;
  }
}

async function restoreStoredChallenge() {
  if (document.visibilityState !== "visible" || challengeRestoreInFlight) return;
  if (typeof state === "undefined" || typeof api !== "function") return;
  const stored = readStoredChallenge();
  if (!stored) {
    releaseInitialSessionCheck();
    if (state.challenge) {
      clearPoll();
      pollChallenge();
    }
    return;
  }

  state.challenge = stored;
  renderConfirmation("Проверяем подтверждение в диалоге с Нэйли…");
  challengeRestoreInFlight = true;
  try {
    clearPoll();
    await pollChallenge();
  } finally {
    challengeRestoreInFlight = false;
  }
}

function applyLoginEnhancements(root = document) {
  applyWeb001eCopy(root);
  addTelegramCodeButton(root);
  bindChallengeReset(root);
}

wrapAuthenticatedRender();
pollChallenge = pollPersistedChallenge;
applyLoginEnhancements();
restoreStoredChallenge();
window.addEventListener("focus", restoreStoredChallenge);
window.addEventListener("pageshow", restoreStoredChallenge);
window.addEventListener("storage", restoreStoredChallenge);
document.addEventListener("visibilitychange", restoreStoredChallenge);
new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node.nodeType === Node.TEXT_NODE) applyLoginEnhancements(node.parentNode);
      if (node.nodeType === Node.ELEMENT_NODE) applyLoginEnhancements(node);
    }
  }
}).observe(document.documentElement, { childList: true, subtree: true });
