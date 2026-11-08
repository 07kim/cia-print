import crypto from "node:crypto";

const COOKIE_NAMES = {
  admin: "cia_print_admin",
  epson: "cia_print_epson",
  oauth: "cia_print_oauth",
};

export function getConfig() {
  return {
    apiKey: process.env.EPSON_API_KEY || "",
    clientId: process.env.EPSON_CLIENT_ID || "",
    clientSecret: process.env.EPSON_CLIENT_SECRET || "",
    redirectUri:
      process.env.EPSON_REDIRECT_URI ||
      "https://print-kappa-one.vercel.app/api/epson/callback",
    sessionSecret: process.env.SESSION_SECRET || "",
    adminPin: process.env.ADMIN_PIN || "",
  };
}

export function isEpsonConfigured(config = getConfig()) {
  return Boolean(
    config.apiKey &&
      config.clientId &&
      config.clientSecret &&
      config.redirectUri &&
      config.sessionSecret.length >= 32,
  );
}

export function parseCookies(req) {
  const source = req.headers.cookie || "";
  return Object.fromEntries(
    source
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const index = part.indexOf("=");
        if (index < 1) return null;
        return [part.slice(0, index), decodeURIComponent(part.slice(index + 1))];
      })
      .filter(Boolean),
  );
}

function cookie(value, options = {}) {
  const parts = [value, "Path=/", "HttpOnly", "SameSite=Lax", "Secure"];
  if (options.maxAge !== undefined) parts.push(`Max-Age=${options.maxAge}`);
  return parts.join("; ");
}

export function setCookie(res, name, value, options) {
  const next = cookie(`${name}=${encodeURIComponent(value)}`, options);
  const current = res.getHeader("Set-Cookie");
  res.setHeader("Set-Cookie", current ? [...[].concat(current), next] : next);
}

export function clearCookie(res, name) {
  setCookie(res, name, "", { maxAge: 0 });
}

function keyFor(secret) {
  return crypto.createHash("sha256").update(secret).digest();
}

export function seal(payload, secret) {
  if (!secret) throw new Error("SESSION_SECRET is not configured");
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", keyFor(secret), iv);
  const plain = Buffer.from(JSON.stringify(payload));
  const encrypted = Buffer.concat([cipher.update(plain), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([iv, tag, encrypted]).toString("base64url");
}

export function unseal(value, secret) {
  if (!value || !secret) return null;
  try {
    const data = Buffer.from(value, "base64url");
    const iv = data.subarray(0, 12);
    const tag = data.subarray(12, 28);
    const encrypted = data.subarray(28);
    const decipher = crypto.createDecipheriv("aes-256-gcm", keyFor(secret), iv);
    decipher.setAuthTag(tag);
    return JSON.parse(Buffer.concat([decipher.update(encrypted), decipher.final()]));
  } catch {
    return null;
  }
}

export function isAdmin(req, config = getConfig()) {
  if (!config.adminPin) return true;
  const session = unseal(parseCookies(req)[COOKIE_NAMES.admin], config.sessionSecret);
  return Boolean(session?.admin && session.expiresAt > Date.now());
}

export function requireAdmin(req, res, config = getConfig()) {
  if (isAdmin(req, config)) return true;
  res.status(401).json({ ok: false, code: "ADMIN_AUTH_REQUIRED" });
  return false;
}

export function setAdminSession(res, config = getConfig()) {
  setCookie(
    res,
    COOKIE_NAMES.admin,
    seal({ admin: true, expiresAt: Date.now() + 8 * 60 * 60 * 1000 }, config.sessionSecret),
    { maxAge: 8 * 60 * 60 },
  );
}

export function getEpsonSession(req, config = getConfig()) {
  return unseal(parseCookies(req)[COOKIE_NAMES.epson], config.sessionSecret);
}

export function setEpsonSession(res, tokens, config = getConfig()) {
  const expiresAt = Date.now() + Math.max(60, Number(tokens.expires_in || 3600) - 60) * 1000;
  setCookie(
    res,
    COOKIE_NAMES.epson,
    seal(
      {
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        expiresAt,
      },
      config.sessionSecret,
    ),
    { maxAge: 30 * 24 * 60 * 60 },
  );
}

export function clearEpsonSession(res) {
  clearCookie(res, COOKIE_NAMES.epson);
}

export function setOAuthState(res, state, config = getConfig()) {
  setCookie(
    res,
    COOKIE_NAMES.oauth,
    seal({ state, expiresAt: Date.now() + 10 * 60 * 1000 }, config.sessionSecret),
    { maxAge: 10 * 60 },
  );
}

export function consumeOAuthState(req, res, state, config = getConfig()) {
  const saved = unseal(parseCookies(req)[COOKIE_NAMES.oauth], config.sessionSecret);
  clearCookie(res, COOKIE_NAMES.oauth);
  return Boolean(saved?.state === state && saved.expiresAt > Date.now());
}

async function tokenRequest(params, config = getConfig()) {
  const basic = Buffer.from(`${config.clientId}:${config.clientSecret}`).toString("base64");
  const response = await fetch("https://auth.epsonconnect.com/auth/token", {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams(params),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error_description || data.error || "Epson authentication failed");
  return data;
}

export function exchangeAuthorizationCode(code, config = getConfig()) {
  return tokenRequest(
    {
      grant_type: "authorization_code",
      code,
      redirect_uri: config.redirectUri,
      client_id: config.clientId,
    },
    config,
  );
}

export async function getAccessToken(req, res, config = getConfig()) {
  const session = getEpsonSession(req, config);
  if (!session?.refreshToken) return null;
  if (session.accessToken && session.expiresAt > Date.now()) return session.accessToken;
  const tokens = await tokenRequest(
    { grant_type: "refresh_token", refresh_token: session.refreshToken },
    config,
  );
  setEpsonSession(res, tokens, config);
  return tokens.access_token;
}

export async function epsonFetch(path, accessToken, config = getConfig(), options = {}) {
  const response = await fetch(`https://api.epsonconnect.com/api/2${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "x-api-key": config.apiKey,
      ...(options.body && !(options.body instanceof Buffer)
        ? { "Content-Type": "application/json" }
        : {}),
      ...options.headers,
    },
  });
  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text.slice(0, 240) };
    }
  }
  if (!response.ok) {
    const error = new Error(data.message || data.error || `Epson API error (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export function method(req, res, allowed) {
  if (req.method === allowed) return true;
  res.setHeader("Allow", allowed);
  res.status(405).json({ ok: false, code: "METHOD_NOT_ALLOWED" });
  return false;
}

export function safeError(res, error) {
  console.error(error);
  res.status(error.status || 500).json({
    ok: false,
    code: "REQUEST_FAILED",
    message: "処理を完了できませんでした。設定または接続状態を確認してください。",
  });
}

export { COOKIE_NAMES };

