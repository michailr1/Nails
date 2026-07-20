const TELEGRAM_BOT_USERNAME = "smartnails_bot";

const replacements = new Map([
  [
    "Мы покажем число для сверки и отправим запрос в закрытый бот. В Telegram достаточно нажать «Подтвердить».",
    "Мы покажем шестизначное число. Отправьте его Нэйли в закрытом Telegram-боте и подтвердите вход в диалоге.",
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
    "Нажмите кнопку под числом. Telegram откроет диалог с Нэйли и подставит готовое сообщение. Вам останется его отправить и отдельно подтвердить вход.",
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

  const button = document.createElement("button");
  button.id = "send-code-to-naily";
  button.className = "primary-button";
  button.type = "button";
  button.textContent = "Отправить код Нэйли";
  button.style.margin = "20px 0 16px";
  button.addEventListener("click", () => {
    const message = `Нэйли, подтверди вход: ${code}`;
    window.location.href = `https://t.me/${TELEGRAM_BOT_USERNAME}?text=${encodeURIComponent(message)}`;
  });

  verificationNumber.insertAdjacentElement("afterend", button);
}

function applyLoginEnhancements(root = document) {
  applyWeb001eCopy(root);
  addTelegramCodeButton(root);
}

applyLoginEnhancements();
new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node.nodeType === Node.TEXT_NODE) applyLoginEnhancements(node.parentNode);
      if (node.nodeType === Node.ELEMENT_NODE) applyLoginEnhancements(node);
    }
  }
}).observe(document.documentElement, { childList: true, subtree: true });
