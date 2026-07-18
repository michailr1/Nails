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
    "Напишите Нэйли в закрытом боте: «подтверди вход» и укажите число с экрана. Нэйли повторит его и попросит отдельное подтверждение.",
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

applyWeb001eCopy();
new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node.nodeType === Node.TEXT_NODE) applyWeb001eCopy(node.parentNode);
      if (node.nodeType === Node.ELEMENT_NODE) applyWeb001eCopy(node);
    }
  }
}).observe(document.documentElement, { childList: true, subtree: true });
