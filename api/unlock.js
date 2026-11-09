import { issueParticipantToken, onlinePassword } from "./_lib/participant.js";

export default function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ ok: false });
  if (String(req.body?.password || "") !== onlinePassword()) {
    return res.status(401).json({ ok: false, message: "パスワードが間違っています。" });
  }
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({ ok: true, token: issueParticipantToken(), expiresIn: 60 });
}
