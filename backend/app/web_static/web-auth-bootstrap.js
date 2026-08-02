const LOGIN_CHALLENGE_BOOTSTRAP_KEY = "nails.web-login.pending-challenge";
const nativeFetch = window.fetch.bind(window);
let gatedSessionRequest = null;
let challengeGateActive = Boolean(localStorage.getItem(LOGIN_CHALLENGE_BOOTSTRAP_KEY));
let routeGateActive = true;

function releaseInitialSessionCheck() {
  if (challengeGateActive || routeGateActive || !gatedSessionRequest) return false;
  const { input, options, resolve, reject } = gatedSessionRequest;
  gatedSessionRequest = null;
  nativeFetch(input, options).then(resolve, reject);
  return true;
}

window.__nailsWebAuthBootstrap = {
  releaseSessionCheck() {
    challengeGateActive = false;
    return releaseInitialSessionCheck();
  },
  releaseRouteCheck() {
    routeGateActive = false;
    return releaseInitialSessionCheck();
  },
};

window.fetch = (input, options = {}) => {
  const requestUrl = typeof input === "string" ? input : input.url;
  const requestMethod = String(options.method || "GET").toUpperCase();
  const isInitialSessionCheck = requestMethod === "GET"
    && new URL(requestUrl, window.location.origin).pathname === "/web/api/auth/session";

  if ((challengeGateActive || routeGateActive) && isInitialSessionCheck && !gatedSessionRequest) {
    return new Promise((resolve, reject) => {
      gatedSessionRequest = { input, options, resolve, reject };
    });
  }
  return nativeFetch(input, options);
};
