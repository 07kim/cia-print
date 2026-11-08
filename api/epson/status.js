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
  if (!method(req, res, "GET")) return;
  const config = getConfig();
  if (!requireAdmin(req, res, config)) return;
  res.setHeader("Cache-Control", "no-store");
  if (!isEpsonConfigured(config)) {
    return res.status(200).json({ ok: true, configured: false, authorized: false });
  }
  try {
    const token = await getAccessToken(req, res, config);
    if (!token) return res.status(200).json({ ok: true, configured: true, authorized: false });
    const device = await epsonFetch("/printing/devices/info", token, config);
    res.status(200).json({
      ok: true,
      configured: true,
      authorized: true,
      device: {
        productName: device.productName || "EPSON printer",
        serialNumber: device.serialNumber
          ? `${"*".repeat(Math.max(0, device.serialNumber.length - 4))}${device.serialNumber.slice(-4)}`
          : "-",
        connected: Boolean(device.connected),
      },
    });
  } catch (error) {
    safeError(res, error);
  }
}

