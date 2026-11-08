from pathlib import Path
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parents[1]
output = root / "assets" / "connection-test.pdf"
output.parent.mkdir(parents=True, exist_ok=True)

width, height = A4
c = canvas.Canvas(str(output), pagesize=A4)
c.setTitle("CIA Print Connection Test")

ink = HexColor("#17283A")
blue = HexColor("#145EA8")
muted = HexColor("#607084")

c.setFillColor(blue)
c.rect(0, height - 24, width, 24, fill=1, stroke=0)

c.setFillColor(ink)
c.setFont("Helvetica-Bold", 26)
c.drawString(54, height - 92, "CIA PRINT")
c.setFont("Helvetica", 11)
c.setFillColor(muted)
c.drawString(54, height - 113, "EPSON CONNECT / CONNECTION TEST")

c.setStrokeColor(HexColor("#C9D2DC"))
c.line(54, height - 137, width - 54, height - 137)

c.setFillColor(ink)
c.setFont("Helvetica-Bold", 18)
c.drawString(54, height - 188, "PRINT CONNECTION VERIFIED")
c.setFont("Helvetica", 12)
c.drawString(54, height - 216, "This sheet was sent from the CIA Print management screen.")

rows = [
    ("PAPER", "A4"),
    ("COLOR", "MONO"),
    ("SIDE", "ONE-SIDED"),
    ("COPIES", "1"),
    ("DEVICE", "EPSON EW-M634T"),
]
y = height - 284
for label, value in rows:
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(muted)
    c.drawString(54, y, label)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(ink)
    c.drawRightString(width - 54, y, value)
    c.setStrokeColor(HexColor("#DDE3E8"))
    c.line(54, y - 11, width - 54, y - 11)
    y -= 48

c.setFillColor(HexColor("#EDF1F4"))
c.roundRect(54, 116, width - 108, 82, 4, fill=1, stroke=0)
c.setFillColor(ink)
c.setFont("Helvetica-Bold", 13)
c.drawString(72, 163, "NEXT")
c.setFont("Helvetica", 10)
c.setFillColor(muted)
c.drawString(72, 143, "If this page is clear and complete, device authorization is ready.")

c.setFillColor(muted)
c.setFont("Helvetica", 8)
c.drawString(54, 52, "DOCUMENT OUTPUT TERMINAL / ADMIN TEST")
c.drawRightString(width - 54, 52, "CIA-PRINT-TEST-001")
c.save()
print(output)

