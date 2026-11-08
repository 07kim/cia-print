import crypto from "node:crypto";
import {
  getConfig,
  isEpsonConfigured,
  requireAdmin,
  setOAuthState,
} from "../_lib/core.js";

export default function handler(req, res) {
  const config = getConfig();
  if (!requireAdmin(req, res, config)) return;
  if (!isEpsonConfigured(config)) return res.redirect(302, "/admin/?error=not-configured");

  const state = crypto.randomBytes(24).toString("base64url");
  setOAuthState(res, state, config);
  const url = new URL("https://auth.epsonconnect.com/auth/authorize");
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", config.clientId);
  url.searchParams.set("redirect_uri", config.redirectUri);
  url.searchParams.set("scope", "device");
  url.searchParams.set("state", state);
  res.redirect(302, url.toString());
}

