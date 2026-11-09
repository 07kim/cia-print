import { validParticipantToken } from "./_lib/participant.js";

export default function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ ok: false });
  const token = String(req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!validParticipantToken(token)) {
    return res.status(401).json({ ok: false, message: "認証の有効期限が切れました。" });
  }
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({ ok: true, preview: true });
}
