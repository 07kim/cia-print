#!/usr/bin/env python3
"""Create the fixed A4 landscape monochrome print PDF."""

from pathlib import Path

from PIL import Image, ImageOps
ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/Users/mayugeyasai/Documents/学友/コンポ 2/黒背景_00003.png")
OUTPUT = ROOT / "output" / "pdf" / "cia-print-a4-monochrome.pdf"
TEMP = ROOT / "tmp" / "pdfs" / "cia-print-a4-monochrome.png"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TEMP.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(SOURCE) as source:
        grayscale = ImageOps.grayscale(source)
        grayscale.save(TEMP, format="PNG", optimize=True)
        # 3508 x 2480 px at 300 dpi is A4 landscape (297 x 210 mm).
        grayscale.save(OUTPUT, format="PDF", resolution=300.0)


if __name__ == "__main__":
    main()
