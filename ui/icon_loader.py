"""Load project and sub-project type images as smooth, cached QPixmaps."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from services.project_service import ProjectService

_cache: dict[tuple[str, int], Optional[QPixmap]] = {}


def load_icon(path: Path | str | None, size: int = 48, dpr: float = 2.0) -> Optional[QPixmap]:
    """Image at path (or a default_icon: name) scaled to fit size px. None if missing or unreadable."""
    if not path:
        return None
    resolved = ProjectService.resolve_icon_path(str(path))
    if resolved is None:
        return None
    key = (str(resolved), size)
    if key in _cache:
        return _cache[key]
    pm = QPixmap(str(resolved))
    if pm.isNull():
        _cache[key] = None
        return None
    px = int(size * dpr)
    pm = pm.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pm.setDevicePixelRatio(dpr)
    _cache[key] = pm
    return pm


def load_type_icon(type_value: str, size: int = 24) -> Optional[QPixmap]:
    """Icon for a sub-project type (assets/icons/<type>.png)."""
    return load_icon(ProjectService.icons_dir() / f"{type_value}.png", size)


def clear_cache() -> None:
    """Forget loaded images (e.g. after the user picked a new project icon)."""
    _cache.clear()


_dark_glyph: dict[int, bool] = {}
_tinted: dict[tuple[int, str], QPixmap] = {}


def _is_dark_glyph(pm: QPixmap) -> bool:
    """True for a near-black, colorless icon (e.g. a black document glyph) that vanishes on dark foam."""
    key = pm.cacheKey()
    if key not in _dark_glyph:
        img = pm.toImage().scaled(24, 24)
        total = lum = sat = 0.0
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.alpha() < 128:
                    continue
                total += 1
                lum += (0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF())
                sat += c.hsvSaturationF() if c.hsvSaturation() >= 0 else 0
        _dark_glyph[key] = bool(total) and lum / total < 0.25 and sat / total < 0.25
    return _dark_glyph[key]


def for_theme(pm: Optional[QPixmap]) -> Optional[QPixmap]:
    """The pixmap, or on the dark theme a dark monochrome glyph re-inked so it stays visible."""
    from PySide6.QtGui import QPainter

    from ui.theme import Theme, t

    if pm is None or not Theme.get().is_dark or not _is_dark_glyph(pm):
        return pm
    color = t("ink_dim")
    key = (pm.cacheKey(), color.name())
    if key not in _tinted:
        tinted = QPixmap(pm.size())
        tinted.setDevicePixelRatio(pm.devicePixelRatio())
        tinted.fill(Qt.GlobalColor.transparent)
        p = QPainter(tinted)
        p.drawPixmap(0, 0, pm)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(tinted.rect(), color)
        p.end()
        _tinted[key] = tinted
    return _tinted[key]
