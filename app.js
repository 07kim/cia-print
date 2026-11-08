const printButton = document.querySelector("#print-button");
const statusMessage = document.querySelector("#status-message");
const statusTitle = document.querySelector("#status-title");
const statusDetail = document.querySelector("#status-detail");
const progress = document.querySelector("#progress");
const progressBar = document.querySelector("#progress-bar");

const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function setStatus(title, detail, kind = "") {
  statusTitle.textContent = title;
  statusDetail.textContent = detail;
  statusMessage.classList.toggle("is-success", kind === "success");
  statusMessage.classList.toggle("is-error", kind === "error");
}

async function runPrintSequence() {
  if (printButton.disabled) return;

  const shouldFail = new URLSearchParams(window.location.search).get("fail") === "1";
  printButton.disabled = true;
  progress.hidden = false;
  progressBar.style.width = "0%";
  setStatus("印刷データを送信しています", "そのままお待ちください");

  requestAnimationFrame(() => {
    progressBar.style.width = "42%";
  });
  await wait(1200);

  if (shouldFail) {
    progressBar.style.width = "100%";
    await wait(500);
    progress.hidden = true;
    setStatus("印刷できませんでした", "お手数ですが、係員へお知らせください", "error");
    printButton.disabled = false;
    printButton.querySelector("span").textContent = "もう一度印刷する";
    return;
  }

  setStatus("印刷しています", "用紙が出るまでお待ちください");
  progressBar.style.width = "78%";
  await wait(1800);
  progressBar.style.width = "100%";
  await wait(650);

  progress.hidden = true;
  setStatus("印刷を開始しました", "印刷された用紙をお取りください", "success");
  printButton.querySelector("span").textContent = "印刷済み";
  printButton.style.background = "var(--green)";
  printButton.style.boxShadow = "0 4px 0 #116242";
}

printButton.addEventListener("click", runPrintSequence);
