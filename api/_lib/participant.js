import crypto from "node:crypto";

const previewSecret = process.env.SESSION_SECRET || "cia-print-online-preview-v1";

function signature(payload) {
  return crypto.createHmac("sha256", previewSecret).update(payload).digest("base64url");
}

export function onlinePassword() {
  return process.env.ACCESS_PASSWORD || "PRINT";
}

export function issueParticipantToken() {
  const payload = Buffer.from(
    JSON.stringify({ expiresAt: Date.now() + 5 * 60 * 1000 }),
  ).toString("base64url");
  return `${payload}.${signature(payload)}`;
}

export function validParticipantToken(value) {
  if (!value || !value.includes(".")) return false;
  const [payload, provided] = value.split(".");
  const expected = signature(payload);
  if (provided.length !== expected.length) return false;
  if (!crypto.timingSafeEqual(Buffer.from(provided), Buffer.from(expected))) return false;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    return Number(data.expiresAt) > Date.now();
  } catch {
    return false;
  }
}
