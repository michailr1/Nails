const TELEGRAM_BOT_USERNAME = "smartnails_bot";

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
    "Нажмите кнопку под числом. Telegram откроется отдельно и подставит готовое подтверждение. После отправки вернитесь в эту вкладку — кабинет откроется автоматически.",
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

function addTelegramCodeButton(root = document) {
  const verificationNumber = root.querySelector?.(".verification-number")
    || document.querySelector(".verification-number");
  if (!verificationNumber || document.querySelector("#send-code-to-naily")) return;

  const code = verificationNumber.textContent.trim();
  if (!/^\d{6}$/.test(code)) return;

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

function resumeChallengePolling() {
  if (document.visibilityState !== "visible") return;
  if (typeof state === "undefined" || !state.challenge) return;
  clearPoll();
  pollChallenge();
}

function applyLoginEnhancements(root = document) {
  applyWeb001eCopy(root);
  addTelegramCodeButton(root);
}

applyLoginEnhancements();
window.addEventListener("focus", resumeChallengePolling);
window.addEventListener("pageshow", resumeChallengePolling);
document.addEventListener("visibilitychange", resumeChallengePolling);
new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node.nodeType === Node.TEXT_NODE) applyLoginEnhancements(node.parentNode);
      if (node.nodeType === Node.ELEMENT_NODE) applyLoginEnhancements(node);
    }
  }
}).observe(document.documentElement, { childList: true, subtree: true });
