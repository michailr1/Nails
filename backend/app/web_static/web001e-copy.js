const TELEGRAM_BOT_USERNAME = "smartnails_bot";
const LOGIN_CHALLENGE_STORAGE_KEY = "nails.web-login.pending-challenge";
let challengeRestoreInFlight = false;

const replacements = new Map([
  [
    "Мы покажем число для сверки и отправим запрос в закрытый бот. В Telegram достаточно нажать «Подтвердить».",
    "Мы покажем шестизначное число. Отправьте его Нэйли в закрытом Telegram-боте — это сразу подтвердит вход.",
  ],
  ["Войти через Telegram", "Получить число"],
  [
    "Код вводить на сайте или в Telegram не нужно.",
    "Число вводится только в переписке с Нэйли. На сайте его вводить не нужно.",
  ],
  ["Сверьте число", "Отправьте число Нэйли"],
  ["Подтвердите вход", "Подтвердите вход в Telegram"],
  [
    "В закрытом Telegram-боте появится запрос с тем же числом.",
    "Нажмите кнопку под числом. Telegram откроется отдельно и подставит готовое подтверждение. После отправки вернитесь на сайт — кабинет откроется автоматически.",
  ],
  [
    "Ожидаем подтверждение в Telegram…",
    "Ждём подтверждение в диалоге с Нэйли…",
  ],
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

function rememberCurrentChallenge() {
  if (typeof state === "undefined" || !state.challenge) return;
  const { challenge_id: challengeId, verification_number: verificationNumber } = state.challenge;
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
  const verificationNumber = root.querySelector?.(".verification-number")
    || document.querySelector(".verification-number");
  if (!verificationNumber || document.querySelector("#send-code-to-naily")) return;

  const code = verificationNumber.textContent.trim();
  if (!/^\d{6}$/.test(code)) return;
  rememberCurrentChallenge();

  const message = `Нэйли, подтверждаю вход: ${code}`;
  const link = document.createElement("a");
  link.id = "send-code-to-naily";
  link.className = "primary-button telegram-code-button";
  link.href = `https://t.me/${TELEGRAM_BOT_USERNAME}?text=${encodeURIComponent(message)}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Отправить код Нэйли";

  verificationNumber.insertAdjacentElement("afterend", link);
}

function bindChallengeReset(root = document) {
  const resetButton = root.querySelector?.("#cancel-login") || document.querySelector("#cancel-login");
  if (!resetButton || resetButton.dataset.challengeResetBound === "true") return;
  resetButton.dataset.challengeResetBound = "true";
  resetButton.addEventListener("click", forgetStoredChallenge, { once: true });
}

async function restoreStoredChallenge() {
  if (document.visibilityState !== "visible" || challengeRestoreInFlight) return;
  if (typeof state === "undefined" || typeof api !== "function") return;

  const stored = readStoredChallenge();
  if (!stored) {
    if (state.challenge) {
      clearPoll();
      pollChallenge();
    }
    return;
  }

  challengeRestoreInFlight = true;
  try {
    const current = await api(`/web/api/auth/challenges/${encodeURIComponent(stored.challenge_id)}`);
    if (["pending", "approved"].includes(current.status)) {
      state.challenge = stored;
      renderConfirmation(
        current.status === "approved"
          ? "Подтверждение получено. Открываем кабинет…"
          : "Ждём подтверждение в диалоге с Нэйли…",
      );
      clearPoll();
      pollChallenge();
      return;
    }
    forgetStoredChallenge();
  } catch (error) {
    if (error.status === 404) forgetStoredChallenge();
  } finally {
    challengeRestoreInFlight = false;
  }
}

function applyLoginEnhancements(root = document) {
  applyWeb001eCopy(root);
  addTelegramCodeButton(root);
  bindChallengeReset(root);
}

applyLoginEnhancements();
window.setTimeout(restoreStoredChallenge, 400);
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
