import {
  clearEpsonSession,
  getConfig,
  method,
  requireAdmin,
} from "../_lib/core.js";

export default function handler(req, res) {
  if (!method(req, res, "POST")) return;
  const config = getConfig();
  if (!requireAdmin(req, res, config)) return;
  clearEpsonSession(res);
  res.status(200).json({ ok: true });
}

