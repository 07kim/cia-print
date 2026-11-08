const ui = {
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
let resetSeconds = 20;
let resetTimer = 0;

async function request(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) throw new Error(data.message || "処理を完了できませんでした。");
  return data;
}

function showScreen(name) {
  ui.lock.hidden = name !== "lock";
  ui.release.hidden = name !== "release";
  ui.resultLayer.hidden = name !== "result";
}

function resetToLock() {
  window.clearInterval(resetTimer);
  token = "";
  ui.password.value = "";
  ui.authMessage.textContent = "英数字で入力してください";
  ui.authMessage.className = "form-message";
  ui.form.classList.remove("is-error");
  ui.printButton.disabled = false;
  ui.resultCard.className = "result-card";
  ui.action.hidden = true;
  ui.countdown.textContent = "";
  showScreen("lock");
}

function showResult(kind, kicker, title, detail) {
  showScreen("result");
  ui.resultCard.className = `result-card ${kind ? `is-${kind}` : ""}`;
  ui.resultKicker.textContent = kicker;
  ui.resultTitle.textContent = title;
  ui.resultDetail.textContent = detail;
  ui.resultSymbol.textContent = { sending: "print", success: "check_circle", error: "error" }[kind] || "print";
  ui.progress.hidden = kind !== "sending";
}

function beginResetCountdown() {
  let remaining = resetSeconds;
  ui.countdown.textContent = `${remaining}秒後にロック画面へ戻ります`;
  resetTimer = window.setInterval(() => {
    remaining -= 1;
    ui.countdown.textContent = `${remaining}秒後にロック画面へ戻ります`;
    if (remaining <= 0) resetToLock();
  }, 1000);
}

ui.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = ui.password.value.trim();
  if (!password) {
    ui.authMessage.textContent = "パスワードを入力してください。";
    return;
  }
  const button = ui.form.querySelector("button");
  button.disabled = true;
  ui.authMessage.textContent = "照合しています…";
  ui.form.classList.remove("is-error");
  try {
    const result = await request("/api/unlock", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    token = result.token;
    showScreen("release");
  } catch (error) {
    ui.form.classList.add("is-error");
    ui.authMessage.className = "form-message is-error";
    ui.authMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

ui.password.addEventListener("input", () => {
  ui.form.classList.remove("is-error");
  ui.authMessage.className = "form-message";
  ui.authMessage.textContent = "英数字で入力してください";
});

ui.printButton.addEventListener("click", async () => {
  if (!token || ui.printButton.disabled) return;
  ui.printButton.disabled = true;
  showResult("sending", "SENDING", "印刷データを送信中", "Macを経由してプリンターへ送信しています。");
  try {
    const result = await request("/api/print", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    token = "";
    window.setTimeout(() => {
      showResult("success", "ACCEPTED", "印刷を受け付けました", "用紙が出てくるまで、そのままお待ちください。");
      ui.action.hidden = false;
      beginResetCountdown();
    }, 850);
  } catch (error) {
    token = "";
    showResult("error", "OUTPUT ERROR", "印刷できませんでした", error.message);
    ui.action.hidden = false;
  }
});

ui.action.addEventListener("click", resetToLock);

request("/api/status")
  .then((status) => {
    resetSeconds = Number(status.resetSeconds) || 20;
    ui.connection.textContent = status.ready ? "Mac・プリンター接続準備完了" : "印刷資料が未設定";
    document.body.classList.toggle("is-offline", !status.ready);
  })
  .catch(() => {
    ui.connection.textContent = "Macへ接続できません";
    document.body.classList.add("is-offline");
  });
