import fs from "node:fs/promises";
import {
  epsonFetch,
  getAccessToken,
  getConfig,
  isEpsonConfigured,
  method,
  requireAdmin,
  safeError,
} from "../_lib/core.js";

export default async function handler(req, res) {
  if (!method(req, res, "POST")) return;
  const config = getConfig();
  if (!requireAdmin(req, res, config)) return;
  if (!isEpsonConfigured(config)) {
    return res.status(503).json({ ok: false, code: "EPSON_NOT_CONFIGURED" });
  }
  try {
    const token = await getAccessToken(req, res, config);
    if (!token) return res.status(401).json({ ok: false, code: "EPSON_AUTH_REQUIRED" });

    const job = await epsonFetch("/printing/jobs", token, config, {
      method: "POST",
      body: JSON.stringify({
        jobName: "CIA_PRINT_CONNECTION_TEST",
        printMode: "document",
        printSettings: {
          paperSize: "ps_a4",
          paperType: "pt_plainpaper",
          borderless: false,
          printQuality: "normal",
          paperSource: "rear",
          colorMode: "mono",
          copies: 1,
        },
      }),
    });

    const pdf = await fs.readFile(new URL("../../assets/connection-test.pdf", import.meta.url));
    const uploadUrl = `${job.uploadUri}${job.uploadUri.includes("?") ? "&" : "?"}File=1.pdf`;
    const upload = await fetch(uploadUrl, {
      method: "POST",
      headers: { "Content-Type": "application/pdf" },
      body: pdf,
    });
    if (!upload.ok) throw new Error(`File upload failed (${upload.status})`);

    await epsonFetch(`/printing/jobs/${encodeURIComponent(job.jobId)}/print`, token, config, {
      method: "POST",
    });
    res.status(200).json({ ok: true, jobId: job.jobId });
  } catch (error) {
    safeError(res, error);
  }
}

