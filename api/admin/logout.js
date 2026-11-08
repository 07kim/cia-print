import { clearCookie, COOKIE_NAMES, method } from "../_lib/core.js";

export default function handler(req, res) {
  if (!method(req, res, "POST")) return;
  clearCookie(res, COOKIE_NAMES.admin);
  res.status(200).json({ ok: true });
}

