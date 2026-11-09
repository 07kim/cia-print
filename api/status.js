export default function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ ok: false });
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({
    ok: true,
    ready: true,
    resetSeconds: 20,
    onlinePreview: true,
  });
}
