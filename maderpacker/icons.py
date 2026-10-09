"""Theme-aware SVG icon loading.

coolicons draw with stroke="currentColor" (dark strokes by default), so they
disappear on dark backgrounds. We recolor at load time based on the system
color scheme; glyphs without an explicit fill (e.g. the GitHub mark) get a
root fill so they follow the scheme too.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

DARK_COLOR = "#FFFFFF"   # stroke/fill used when the system is in dark mode
LIGHT_COLOR = "#1E1E1E"  # stroke/fill used when the system is in light mode


def bundle_path(*parts: str) -> Path:
    """Data file path that works in dev and in the frozen exe."""
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen is not None:
        return Path(frozen, *parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


def recolor_svg(text: str, color: str) -> str:
    """Return SVG text with currentColor (and default-black glyphs) set to color."""
    out = text.replace("currentColor", color)
    head_end = out.find(">")
    head = out[:head_end] if head_end != -1 else ""
    if "fill=" not in head:
        out = out.replace("<svg", f'<svg fill="{color}"', 1)
    return out


def scheme_color(dark: bool) -> str:
    return DARK_COLOR if dark else LIGHT_COLOR


def system_is_dark() -> bool:
    """Qt color scheme when available, else Windows registry, else False."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:  # noqa: BLE001 - fall through to registry
        pass
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
        except OSError:
            pass
    return False


@lru_cache(maxsize=128)
def svg_icon(name: str, dark: bool):
    """Render icons/<name> recolored for the scheme as a QIcon (64px source)."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    path = bundle_path("maderpacker", "icons", name)
    if not path.is_file():
        return QIcon()
    data = recolor_svg(path.read_text(encoding="utf-8"), scheme_color(dark)).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        return QIcon()
    image = QImage(64, 64, QImage.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))


@lru_cache(maxsize=4)
def logo_pixmap(size: int = 96):
    """Render assets/logo.svg full-color as a QPixmap (About dialog logo)."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    path = bundle_path("assets", "logo.svg")
    if not path.is_file():
        return QPixmap()
    renderer = QSvgRenderer(QByteArray(path.read_bytes()))
    if not renderer.isValid():
        return QPixmap()
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)


@lru_cache(maxsize=4)
def logo_icon(size: int = 256):
    """Render assets/logo.svg full-color as a QIcon (window/taskbar icon)."""
    from PySide6.QtGui import QIcon

    return QIcon(logo_pixmap(size))
