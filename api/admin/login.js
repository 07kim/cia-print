import { getConfig, method, setAdminSession } from "../_lib/core.js";

export default function handler(req, res) {
  if (!method(req, res, "POST")) return;
  const config = getConfig();
  if (!config.adminPin) return res.status(200).json({ ok: true });
  if (!config.sessionSecret || config.sessionSecret.length < 32) {
    return res.status(503).json({ ok: false, code: "SESSION_SECRET_REQUIRED" });
  }
  if (String(req.body?.pin || "") !== config.adminPin) {
    return res.status(401).json({ ok: false, code: "INVALID_PIN" });
  }
  setAdminSession(res, config);
  res.status(200).json({ ok: true });
}

