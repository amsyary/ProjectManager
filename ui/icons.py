"""Tool silhouettes: one stroke weight on a 24px grid, rendered in any theme color."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

STROKE = 1.8

_PATHS: dict[str, str] = {
    "code": '<path d="M8.5 7.5 4 12l4.5 4.5M15.5 7.5 20 12l-4.5 4.5M13.6 5l-3.2 14"/>',
    "folder": '<path d="M3.5 7.2c0-.9.7-1.7 1.7-1.7h4l2 2.2h7.6c.9 0 1.7.8 1.7 1.7v8.4c0 .9-.8 1.7-1.7 1.7H5.2c-1 0-1.7-.8-1.7-1.7z"/>',
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><path d="m7 9.5 3 2.5-3 2.5M12.5 15h4.5"/>',
    "run": '<path d="m5 6.5 5.5 5.5L5 17.5M13 18h6.5"/>',
    "tasks": '<path d="m4 6.5 1.5 1.5L8.5 5M4 12.5 5.5 14l3-3M4 18.5 5.5 20l3-3M11.5 7h8.5M11.5 13h8.5M11.5 19h8.5"/>',
    "launch": '<circle cx="12" cy="12" r="8.5"/><path d="M10.2 8.6v6.8l5.3-3.4z"/>',
    "play": '<path d="M7.5 5v14l11-7z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1.6"/>',
    "bolt": '<path d="M13 2.8 5.2 13.4h6.1l-1 7.8 8-10.9h-6.1z"/>',
    "restart": '<path d="M4.6 12a7.4 7.4 0 1 0 2.3-5.4"/><path d="M4.4 3.8v4.6H9"/>',
    "edit": '<path d="m14.4 5.6 4 4M4.5 19.5l1-4.4L15.7 4.9a1.4 1.4 0 0 1 2 0l1.4 1.4a1.4 1.4 0 0 1 0 2L8.9 18.5z"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V4.6h5V7M6.5 7l1 12.4c.1.8.7 1.4 1.5 1.4h6c.8 0 1.4-.6 1.5-1.4l1-12.4M10 11v6M14 11v6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5 5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5.4 5.4 7 7M17 17l1.6 1.6M5.4 18.6 7 17M17 7l1.6-1.6"/>',
    "moon": '<path d="M19.6 14.6A7.6 7.6 0 0 1 9.4 4.4a7.6 7.6 0 1 0 10.2 10.2z"/>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="1.8"/><path d="M15.5 8.5V6c0-.8-.7-1.5-1.5-1.5H6c-.8 0-1.5.7-1.5 1.5v8c0 .8.7 1.5 1.5 1.5h2.5"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "phone": '<rect x="7" y="2.8" width="10" height="18.4" rx="2"/><path d="M10.5 18h3"/>',
    "chevron": '<path d="m7 10 5 5 5-5"/>',
    "more": '<circle cx="5.5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18.5" cy="12" r="1.2"/>',
    "note": '<path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5v5h5M9 12.5h7M9 16h5"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.6 3.4 5.4 3.4 8.5s-1 5.9-3.4 8.5c-2.4-2.6-3.4-5.4-3.4-8.5s1-5.9 3.4-8.5z"/>',
    "file": '<path d="M6.5 3.5h7L18 8v12.5H6.5z"/><path d="M13 3.5v5h5"/>',
    "external": '<path d="M14 4.5h5.5V10M19.5 4.5 11 13M17.5 14v4.5c0 .8-.7 1.5-1.5 1.5H6c-.8 0-1.5-.7-1.5-1.5v-10C4.5 7.7 5.2 7 6 7h4.5"/>',
    "close": '<path d="m6.5 6.5 11 11M17.5 6.5l-11 11"/>',
    "image": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.8"/><path d="m20.5 16-5-5-9 8.5"/>',
    "grid": '<rect x="4" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.2"/>',
    "export": '<path d="M12 15V3.8M7.5 8.3 12 3.8l4.5 4.5M4.5 14v4.5c0 .8.7 1.5 1.5 1.5h12c.8 0 1.5-.7 1.5-1.5V14"/>',
    "import": '<path d="M12 3.8V15M7.5 10.5 12 15l4.5-4.5M4.5 14v4.5c0 .8.7 1.5 1.5 1.5h12c.8 0 1.5-.7 1.5-1.5V14"/>',
    "drawer": '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M3.5 12h17M9.5 8h5M9.5 16h5"/>',
    "pulse": '<path d="M3 12h4l2.5-6.5 5 13 2.5-6.5h4"/>',
    "logs": '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M7 8.5h6M7 12h10M7 15.5h4"/>',
    "tag": '<path d="M3.8 12.6V4.8c0-.6.4-1 1-1h7.8l7.6 7.6a1.4 1.4 0 0 1 0 2l-6.8 6.8a1.4 1.4 0 0 1-2 0z"/><circle cx="8.3" cy="8.3" r="1.4"/>',
    "erase":'<path d="M4.5 7h15M9.5 7V4.6h5V7M6.5 7l1 12.4c.1.8.7 1.4 1.5 1.4h6c.8 0 1.4-.6 1.5-1.4l1-12.4"/>',
}

_FILLED = {"play", "stop", "bolt", "more"}

_cache: dict[tuple, QPixmap] = {}


def _svg(name: str, color: QColor) -> bytes:
    body = _PATHS[name]
    hex_rgb = color.name(QColor.NameFormat.HexRgb)
    opacity = f"{color.alphaF():.3f}"
    fill = hex_rgb if name in _FILLED else "none"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<g fill="{fill}" fill-opacity="{opacity}" stroke="{hex_rgb}" stroke-opacity="{opacity}" '
        f'stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</g></svg>"
    ).encode()


def pixmap(name: str, color: QColor | str, size: int = 16, dpr: float = 2.0) -> QPixmap:
    """The named icon in color, size px square (rendered at dpr for crisp HiDPI)."""
    hex_color = QColor(color).name(QColor.NameFormat.HexArgb)
    key = (name, hex_color, size, dpr)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    renderer = QSvgRenderer(QByteArray(_svg(name, QColor(color))))
    px = int(size * dpr)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(dpr)
    _cache[key] = pm
    return pm


def icon(name: str, color: QColor | str, size: int = 16) -> QIcon:
    return QIcon(pixmap(name, color, size))
