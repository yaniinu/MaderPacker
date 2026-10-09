"""Render assets/logo.svg to PNG + multi-size ICO for the exe icon.

Run headless: .venv/Scripts/python tools/make_icon.py
Requires PySide6 (QtSvg) and Pillow. Offscreen platform is forced.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "logo.svg"
PNG = ROOT / "assets" / "logo.png"
ICO = ROOT / "assets" / "logo.ico"


def main() -> None:
    app = QApplication([])
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        raise SystemExit("logo.svg failed to render")
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(0)
    from PySide6.QtGui import QPainter
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    if not image.save(str(PNG), "PNG"):
        raise SystemExit("could not write logo.png")
    with Image.open(PNG) as im:
        im.save(ICO, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print(f"wrote {PNG} ({PNG.stat().st_size} bytes)")
    print(f"wrote {ICO} ({ICO.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
