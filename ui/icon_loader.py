"""Load and resize images for tkinter display."""

from pathlib import Path
from typing import Optional

from PIL import Image, ImageTk

from services.project_service import ProjectService


def load_icon(path: Path | str | None, size: tuple[int, int] = (48, 48)):
    """
    Load an image and resize for tkinter. Returns ImageTk.PhotoImage or None.
    Resolves default_icon: paths via ProjectService.resolve_icon_path.
    """
    if not path:
        return None
    resolved = ProjectService.resolve_icon_path(str(path))
    if resolved is None:
        return None
    p = resolved
    try:
        img = Image.open(p).convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def load_type_icon(icons_dir: Path, type_value: str, size: tuple[int, int] = (24, 24)):
    """Load icon for a project type (e.g. flutter.png)."""
    filename = f"{type_value}.png"
    return load_icon(icons_dir / filename, size)
