const $ = (selector) => document.querySelector(selector);
const ui = {
  dashboard: $("#dashboard"), dashboardMessage: $("#dashboard-message"),
  status: $("#status-copy"), settingsForm: $("#settings-form"), uploadForm: $("#upload-form"),
  password: $("#access-password"), printer: $("#printer-name"), reset: $("#reset-seconds"),
  cooldown: $("#cooldown-seconds"), documentName: $("#document-name"),
  file: $("#document-file"), reprint: $("#reprint"),
};

async function api(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store", ...options,
    headers: { ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) throw new Error(data.message || "処理に失敗しました。");
  return data;
}

function message(text, error = false) {
  ui.dashboardMessage.textContent = text;
  ui.dashboardMessage.classList.toggle("error", error);
}

async function loadDashboard() {
  const config = await api("/api/admin/config");
  ui.password.value = config.accessPassword;
  ui.printer.value = config.printerName;
  ui.reset.value = config.resetSeconds;
  ui.cooldown.value = config.cooldownSeconds;
  ui.documentName.textContent = config.documentName;
  ui.status.textContent = `${config.printerName} / ${config.documentName}`;
}

ui.settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  message("保存しています…");
  try {
    const result = await api("/api/admin/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        accessPassword: ui.password.value.trim(),
        printerName: ui.printer.value.trim(),
        resetSeconds: Number(ui.reset.value),
        cooldownSeconds: Number(ui.cooldown.value),
      }),
    });
    message(result.message);
  } catch (error) { message(error.message, true); }
});

ui.uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = new FormData();
  body.append("document", ui.file.files[0]);
  message("印刷資料を保存しています…");
  try {
    const result = await api("/api/admin/upload", { method: "POST", body });
    message(result.message);
    ui.file.value = "";
    await loadDashboard();
  } catch (error) { message(error.message, true); }
});

ui.reprint.addEventListener("click", async () => {
  if (!window.confirm("現在の固定資料を1部印刷しますか？")) return;
  ui.reprint.disabled = true;
  message("プリンターへ送信しています…");
  try {
    const result = await api("/api/admin/print", { method: "POST" });
    message(`再印刷を受け付けました。 ${result.message}`);
  } catch (error) { message(error.message, true); }
  finally { ui.reprint.disabled = false; }
});

loadDashboard().catch((error) => message(error.message, true));
