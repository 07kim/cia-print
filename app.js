const ui = {
  home: document.querySelector("#home-screen"),
  homeAction: document.querySelector("#home-action"),
  lock: document.querySelector("#lock-screen"),
  release: document.querySelector("#release-screen"),
  form: document.querySelector("#auth-form"),
  password: document.querySelector("#password"),
  authMessage: document.querySelector("#auth-message"),
  printButton: document.querySelector("#print-button"),
  resultLayer: document.querySelector("#result-layer"),
  resultCard: document.querySelector("#result-card"),
  resultSymbol: document.querySelector("#result-symbol .material-symbols-rounded"),
  resultKicker: document.querySelector("#result-kicker"),
  resultTitle: document.querySelector("#result-title"),
  resultDetail: document.querySelector("#result-detail"),
  progress: document.querySelector("#send-progress"),
  action: document.querySelector("#result-action"),
  countdown: document.querySelector("#countdown"),
  connection: document.querySelector("#connection-label"),
};

let token = "";
let resetSeconds = 7;
let resetTimer = 0;
let authorizationTimer = 0;
let lockIdleTimer = 0;
const AUTH_CHECK_MINIMUM_MS = 350;
const CONNECTION_DISPLAY_MS = 200;
const SENDING_DISPLAY_MS = 6000;
const LOCK_IDLE_TIMEOUT_MS = 8000;

const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

async function request(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error("Macとの通信が切れました。MacでCIA Printが起動しているか、同じWi-Fi/テザリングに接続されているか確認してください。");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    if (response.status === 401) {
      throw new Error(data.message || "認証できませんでした。パスワードまたは有効期限を確認してください。");
    }
    if (response.status === 429) {
      throw new Error(data.message || "連続印刷の制限中です。少し時間をおいて再試行してください。");
    }
    if (response.status >= 500) {
      throw new Error("Macのサーバーでエラーが発生しました。Macのターミナルに表示された内容を確認してください。");
    }
    throw new Error(data.message || "通信に失敗しました。接続状態を確認して再試行してください。");
  }
  return data;
}

function showScreen(name) {
  ui.home.hidden = name !== "home";
  ui.lock.hidden = name !== "lock";
  ui.release.hidden = name !== "release";
  ui.resultLayer.hidden = name !== "result";
}

function screenElement(name) {
  return {
    home: ui.home,
    lock: ui.lock,
    release: ui.release,
    result: ui.resultLayer,
  }[name];
}

async function transitionTo(name) {
  const incoming = screenElement(name);
  const outgoing = [ui.home, ui.lock, ui.release, ui.resultLayer]
    .find((element) => !element.hidden);
  if (!incoming || outgoing === incoming) return;
  if (reduceMotion.matches) {
    showScreen(name);
    return;
  }
  if (outgoing) {
    await outgoing.animate(
      [
        { opacity: 1, transform: "translateY(0) scale(1)" },
        { opacity: 0, transform: "translateY(-8px) scale(.985)" },
      ],
      { duration: 220, easing: "cubic-bezier(.4,0,1,1)", fill: "forwards" },
    ).finished.catch(() => {});
  }
  showScreen(name);
  await incoming.animate(
    [
      { opacity: 0, transform: "translateY(12px) scale(.985)" },
      { opacity: 1, transform: "translateY(0) scale(1)" },
    ],
    { duration: 420, easing: "cubic-bezier(.2,.8,.2,1)", fill: "both" },
  ).finished.catch(() => {});
}

async function resetToHome() {
  window.clearInterval(resetTimer);
  window.clearTimeout(authorizationTimer);
  window.clearTimeout(lockIdleTimer);
  token = "";
  ui.password.value = "";
  ui.authMessage.textContent = "";
  ui.authMessage.className = "form-message";
  ui.form.classList.remove("is-error");
  ui.form.classList.remove("is-checking");
  ui.lock.classList.remove("is-input-ready");
  ui.printButton.disabled = false;
  await transitionTo("home");
  // The result layer must be hidden before its success/error styling is reset.
  // Resetting it while visible caused a brief red card flash during the return home.
  ui.resultCard.className = "result-card";
  ui.action.hidden = true;
  ui.countdown.textContent = "";
}

function restartLockIdleTimer() {
  window.clearTimeout(lockIdleTimer);
  lockIdleTimer = window.setTimeout(() => {
    if (!ui.lock.hidden) resetToHome();
  }, LOCK_IDLE_TIMEOUT_MS);
}

async function openPasswordScreen() {
  if (ui.homeAction.disabled) return;
  ui.homeAction.disabled = true;
  await transitionTo("lock");
  if (!reduceMotion.matches) await wait(40);
  ui.lock.classList.add("is-input-ready");
  restartLockIdleTimer();
  ui.homeAction.disabled = false;
}

async function showResult(kind, kicker, title, detail) {
  const alreadyVisible = !ui.resultLayer.hidden;
  if (!alreadyVisible) await transitionTo("result");
  ui.resultCard.className = `result-card ${kind ? `is-${kind}` : ""}`;
  ui.resultKicker.textContent = kicker;
  ui.resultTitle.textContent = title;
  ui.resultDetail.textContent = detail;
  ui.resultSymbol.textContent = { sending: "print", success: "check_circle", error: "error" }[kind] || "print";
  ui.progress.hidden = kind !== "sending";
  if (alreadyVisible && !reduceMotion.matches) {
    ui.resultCard.animate(
      [
        { opacity: .25, transform: "translateY(6px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 360, easing: "cubic-bezier(.2,.8,.2,1)" },
    );
  }
}

function beginResetCountdown() {
  let remaining = resetSeconds;
  ui.countdown.textContent = `${remaining}秒後にプリンター画面へ戻ります`;
  resetTimer = window.setInterval(() => {
    remaining -= 1;
    ui.countdown.textContent = `${remaining}秒後にプリンター画面へ戻ります`;
    if (remaining <= 0) resetToHome();
  }, 1000);
}

ui.homeAction.addEventListener("click", openPasswordScreen);

ui.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = ui.password.value.trim();
  if (!password) {
    ui.authMessage.textContent = "パスワードを入力してください。";
    return;
  }
  window.clearTimeout(lockIdleTimer);
  const button = ui.form.querySelector("button");
  button.disabled = true;
  ui.authMessage.textContent = "照合しています…";
  ui.authMessage.className = "form-message is-checking";
  ui.form.classList.remove("is-error");
  ui.form.classList.add("is-checking");
  const startedAt = performance.now();
  try {
    const result = await request("/api/unlock", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    await wait(Math.max(0, AUTH_CHECK_MINIMUM_MS - (performance.now() - startedAt)));
    if (result.admin) {
      window.location.assign("/admin/");
      return;
    }
    ui.authMessage.textContent = "プリンターに接続しています…";
    await wait(CONNECTION_DISPLAY_MS);
    token = result.token;
    window.clearTimeout(authorizationTimer);
    authorizationTimer = window.setTimeout(() => {
      if (token) resetToHome();
    }, Math.max(1, Number(result.expiresIn) || 60) * 1000);
    await transitionTo("release");
  } catch (error) {
    await wait(Math.max(0, AUTH_CHECK_MINIMUM_MS - (performance.now() - startedAt)));
    ui.form.classList.add("is-error");
    ui.authMessage.className = "form-message is-error";
    ui.authMessage.textContent = error.message.includes("パスワード")
      ? "パスワードが間違っています。"
      : error.message;
    restartLockIdleTimer();
  } finally {
    ui.form.classList.remove("is-checking");
    button.disabled = false;
  }
});

ui.password.addEventListener("input", () => {
  restartLockIdleTimer();
  ui.form.classList.remove("is-error");
  ui.form.classList.remove("is-checking");
  ui.authMessage.className = "form-message";
  ui.authMessage.textContent = "";
});

ui.lock.addEventListener("pointerdown", restartLockIdleTimer);
ui.lock.addEventListener("keydown", restartLockIdleTimer);

ui.printButton.addEventListener("click", async () => {
  if (!token || ui.printButton.disabled) return;
  window.clearTimeout(authorizationTimer);
  ui.printButton.disabled = true;
  const sendingStartedAt = performance.now();
  await showResult("sending", "SENDING", "送信中", "プリンターへ送信しています。");
  try {
    const result = await request("/api/print", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    token = "";
    await wait(Math.max(0, SENDING_DISPLAY_MS - (performance.now() - sendingStartedAt)));
    await showResult("success", "ACCEPTED", "受付完了", "そのままお待ちください。");
    ui.action.hidden = false;
    beginResetCountdown();
  } catch (error) {
    token = "";
    await showResult("error", "OUTPUT ERROR", "印刷できませんでした", error.message);
    ui.action.hidden = false;
  }
});

ui.action.addEventListener("click", resetToHome);

request("/api/status")
  .then((status) => {
    resetSeconds = Number(status.resetSeconds) || 7;
    ui.connection.textContent = status.ready ? "Macに接続済み・印刷資料あり" : "印刷資料が未設定";
    document.body.classList.toggle("is-offline", !status.ready);
  })
  .catch(() => {
    ui.connection.textContent = "Macへ接続できません。Wi-Fiとサーバーを確認";
    document.body.classList.add("is-offline");
  });
