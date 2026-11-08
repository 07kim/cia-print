import {
  consumeOAuthState,
  exchangeAuthorizationCode,
  getConfig,
  setEpsonSession,
} from "../_lib/core.js";

export default async function handler(req, res) {
  const config = getConfig();
  const code = String(req.query.code || "");
  const state = String(req.query.state || "");
  if (!code || !consumeOAuthState(req, res, state, config)) {
    return res.redirect(302, "/admin/?error=oauth-state");
  }
  try {
    const tokens = await exchangeAuthorizationCode(code, config);
    setEpsonSession(res, tokens, config);
    res.redirect(302, "/admin/?connected=1");
  } catch (error) {
    console.error(error);
    res.redirect(302, "/admin/?error=oauth-token");
  }
}

