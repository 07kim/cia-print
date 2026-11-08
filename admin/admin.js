const elements = {
  loginPanel: document.querySelector("#login-panel"),
  loginForm: document.querySelector("#login-form"),
  loginFeedback: document.querySelector("#login-feedback"),
  dashboard: document.querySelector("#dashboard"),
  statusDot: document.querySelector("#status-dot"),
  statusLabel: document.querySelector("#status-label"),
  statusDetail: document.querySelector("#status-detail"),
  configured: document.querySelector("#configured-value"),
  authorized: document.querySelector("#authorized-value"),
  connected: document.querySelector("#connected-value"),
  product: document.querySelector("#product-value"),
  serial: document.querySelector("#serial-value"),
  redirectUri: document.querySelector("#redirect-uri"),
  refresh: document.querySelector("#refresh-button"),
  connect: document.querySelector("#connect-button"),
  disconnect: document.querySelector("#disconnect-button"),
  testPrint: document.querySelector("#test-print-button"),
  jobResult: document.querySelector("#job-result strong"),
  copyUri: document.querySelector("#copy-uri"),
};

async function json(url, options) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.message || "Request failed");
    error.code = data.code;
    throw error;
  }
  return data;
}

function setOverview(kind, label, detail) {
  elements.statusDot.className = `status-dot${kind ? ` is-${kind}` : ""}`;
  elements.statusLabel.textContent = label;
  elements.statusDetail.textContent = detail;
}

async function load() {
  const config = await json("/api/config");
  elements.redirectUri.textContent = config.redirectUri;
  if (!config.authenticated) {
    elements.loginPanel.hidden = false;
    elements.dashboard.hidden = true;
    return;
  }
  elements.loginPanel.hidden = true;
  elements.dashboard.hidden = false;
  await refreshStatus();
}

async function refreshStatus() {
  elements.refresh.disabled = true;
  setOverview("", "確認中", "プリンター状態を取得しています");
  try {
    const status = await json("/api/epson/status");
    elements.configured.textContent = status.configured ? "設定済み" : "未設定";
    elements.authorized.textContent = status.authorized ? "認証済み" : "未認証";
    elements.connected.textContent = status.device?.connected ? "オンライン" : "-";
    elements.product.textContent = status.device?.productName || "-";
    elements.serial.textContent = status.device?.serialNumber || "-";
    elements.connect.hidden = !status.configured || status.authorized;
    elements.disconnect.disabled = !status.authorized;
    elements.testPrint.disabled = !status.device?.connected;
    if (!status.configured) {
      setOverview("error", "API設定が必要です", "VercelへEpson Connectの認証情報を登録してください");
    } else if (!status.authorized) {
      setOverview("", "プリンター未認証", "Epsonで認証を押して使用する機器を選んでください");
    } else if (!status.device?.connected) {
      setOverview("error", "プリンターはオフラインです", "電源とインターネット接続を確認してください");
    } else {
      setOverview("online", "プリンター接続済み", "テスト印刷を実行できます");
    }
  } catch (error) {
    if (error.code === "ADMIN_AUTH_REQUIRED") return load();
    setOverview("error", "状態を確認できません", "時間を置いて再確認してください");
  } finally {
    elements.refresh.disabled = false;
  }
}

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.loginFeedback.textContent = "";
  try {
    await json("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ pin: new FormData(elements.loginForm).get("pin") }),
    });
    await load();
  } catch {
    elements.loginFeedback.textContent = "PINが一致しません。";
  }
});

elements.refresh.addEventListener("click", refreshStatus);
elements.disconnect.addEventListener("click", async () => {
  await json("/api/epson/disconnect", { method: "POST" });
  elements.jobResult.textContent = "接続を解除しました";
  await refreshStatus();
});
elements.testPrint.addEventListener("click", async () => {
  elements.testPrint.disabled = true;
  elements.testPrint.textContent = "送信中...";
  elements.jobResult.textContent = "印刷データを送信しています";
  try {
    const result = await json("/api/epson/test-print", { method: "POST" });
    elements.jobResult.textContent = `送信完了 / JOB ${result.jobId}`;
  } catch {
    elements.jobResult.textContent = "送信に失敗しました";
  } finally {
    elements.testPrint.textContent = "テスト印刷";
    await refreshStatus();
  }
});
elements.copyUri.addEventListener("click", async () => {
  await navigator.clipboard.writeText(elements.redirectUri.textContent);
  elements.copyUri.textContent = "コピー済み";
  window.setTimeout(() => (elements.copyUri.textContent = "コピー"), 1400);
});

const query = new URLSearchParams(location.search);
if (query.get("connected") === "1") elements.jobResult.textContent = "Epson認証が完了しました";
if (query.has("error")) setOverview("error", "認証を完了できませんでした", "設定を確認してもう一度お試しください");
load().catch(() => setOverview("error", "管理画面を読み込めません", "再読み込みしてください"));

