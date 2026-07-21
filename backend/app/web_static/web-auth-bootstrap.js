const LOGIN_CHALLENGE_BOOTSTRAP_KEY = "nails.web-login.pending-challenge";
const nativeFetch = window.fetch.bind(window);
let gatedSessionRequest = null;
let gateSessionBootstrap = Boolean(localStorage.getItem(LOGIN_CHALLENGE_BOOTSTRAP_KEY));

window.__nailsWebAuthBootstrap = {
  releaseSessionCheck() {
    gateSessionBootstrap = false;
    if (!gatedSessionRequest) return false;
    const { input, options, resolve, reject } = gatedSessionRequest;
    gatedSessionRequest = null;
    nativeFetch(input, options).then(resolve, reject);
    return true;
  },
  discardSessionCheck() {
    gateSessionBootstrap = false;
    gatedSessionRequest = null;
  },
  verifySession() {
    return nativeFetch("/web/api/auth/session", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  },
};

window.fetch = (input, options = {}) => {
  const requestUrl = typeof input === "string" ? input : input.url;
  const requestMethod = String(options.method || "GET").toUpperCase();
  const isInitialSessionCheck = requestMethod === "GET"
    && new URL(requestUrl, window.location.origin).pathname === "/web/api/auth/session";

  if (gateSessionBootstrap && isInitialSessionCheck && !gatedSessionRequest) {
    return new Promise((resolve, reject) => {
      gatedSessionRequest = { input, options, resolve, reject };
    });
  }
  return nativeFetch(input, options);
};
