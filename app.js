const printButton = document.querySelector("#print-button");
const statusMessage = document.querySelector("#status-message");
const statusTitle = document.querySelector("#status-title");
const statusDetail = document.querySelector("#status-detail");
const progress = document.querySelector("#progress");
const progressBar = document.querySelector("#progress-bar");

function setStatus(title, detail, kind = "") {
  statusTitle.textContent = title;
  statusDetail.textContent = detail;
  statusMessage.classList.toggle("is-success", kind === "success");
  statusMessage.classList.toggle("is-error", kind === "error");
}

async function runPrintSequence() {
  if (printButton.disabled) return;

  printButton.disabled = true;
  progress.hidden = false;
  progressBar.style.width = "0%";
  setStatus("印刷データを送信しています", "そのままお待ちください");
  const requestId = window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;

  requestAnimationFrame(() => {
    progressBar.style.width = "70%";
  });

  try {
    const response = await fetch("/api/print", {
      method: "POST",
      headers: { "X-Request-ID": requestId },
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.message || "印刷指示を送信できませんでした。");

    progressBar.style.width = "100%";
    window.setTimeout(() => { progress.hidden = true; }, 350);
    setStatus("印刷指示を送信しました", "用紙が出てくるまでお待ちください", "success");
    printButton.querySelector("span").textContent = "送信済み";
    printButton.style.background = "var(--green)";
    printButton.style.boxShadow = "0 4px 0 #116242";
  } catch (error) {
    progress.hidden = true;
    setStatus("印刷できませんでした", error.message || "係員へお知らせください", "error");
    printButton.disabled = false;
    printButton.querySelector("span").textContent = "もう一度送信する";
  }
}

printButton.addEventListener("click", runPrintSequence);

fetch("/api/status", { cache: "no-store" })
  .then((response) => response.json())
  .then((status) => {
    if (!status.ready) throw new Error();
  })
  .catch(() => {
    setStatus("プリンターへ接続できません", "係員へお知らせください", "error");
    printButton.disabled = true;
  });
