import { getConfig, isAdmin, isEpsonConfigured, method } from "./_lib/core.js";

export default function handler(req, res) {
  if (!method(req, res, "GET")) return;
  const config = getConfig();
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({
    ok: true,
    configured: isEpsonConfigured(config),
    adminPinEnabled: Boolean(config.adminPin),
    authenticated: isAdmin(req, config),
    redirectUri: config.redirectUri,
  });
}

