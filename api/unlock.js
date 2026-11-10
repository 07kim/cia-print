import { issueParticipantToken, onlinePassword } from "./_lib/participant.js";

const ADMIN_ENTRY_PASSWORD = "admin0000";

export default function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ ok: false });
  const password = String(req.body?.password || "");
  res.setHeader("Cache-Control", "no-store");
  if (password === ADMIN_ENTRY_PASSWORD) {
    return res.status(200).json({ ok: true, admin: true });
  }
  if (password !== onlinePassword()) {
    return res.status(401).json({ ok: false, message: "パスワードが間違っています。" });
  }
  res.status(200).json({ ok: true, token: issueParticipantToken(), expiresIn: 60 });
}
