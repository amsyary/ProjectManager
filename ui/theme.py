"""Design tokens, fonts, foam texture and the Qt stylesheet for both themes.

DIRECTION CONTRACT (seed 95fc6175)
THESIS: Each project is a tool drawer; every folder is a foam slot and every action it can
    perform is a tool sitting in its own cut-out. Refuses the VS Code clone of grey panels and
    blue buttons.
OWN-WORLD: Two-layer Kaizen foam. Matte charcoal (light: pale grey) top layer, a flat chrome-yellow
    under-layer that only shows where something is cut away: primary actions, focus, checked
    states, and tools that are "out" (running). Dymo-embossed label tape for names, DIN
    (Bahnschrift) for every label, Cascadia Mono only for paths, commands and logs.
STORY: Open the app, type three letters, the drawer slides open, one click launches the editor,
    terminal, task or Flutter run. A running app shows as an empty yellow slot.
FIRST VIEWPORT: Left rail of drawer fronts (search on top, Add project at the bottom); the open
    drawer fills the rest: a header slab with the reversed tape name and project tools, then one
    foam slab per folder with its tools cut in. Top strip: editor, terminal, scrcpy, snippets.
FORM: Kaizen shadow board, candidate 3 of 7. Raises: two text sizes only in a drawer (rank by
    weight, case and reversal: timetable); folders ranked by apparatus, not size (lexicon).
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
    verdict, DESIGN.md, and every shipping raster carrying its provenance
"""

from __future__ import annotations

import random
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

DARK: dict[str, str] = {
    "cabinet": "#16181B",  # Window ground: the cabinet body
    "rail": "#1C1E22",  # Top strip and drawer rail
    "foam": "#26292D",  # Foam top layer: panels and drawer fronts
    "foam_hi": "#2D3035",  # Hovered / pulled-out foam
    "cut": "#131518",  # Floor of a cut-out: inputs and tool slots
    "cut_hi": "#1C1F23",  # Hovered cut-out floor
    "wall_dark": "#08090A",  # Shadowed upper wall of a cut-out
    "wall_light": "#383C42",  # Lit lower lip of a cut-out
    "edge": "#33373D",  # Hairline edge of a foam panel
    "shadow": "#000000",
    "ink": "#ECE8E0",
    "ink_dim": "#A6A49D",
    "ink_faint": "#8E8D88",
    "yellow": "#F2B705",
    "yellow_hi": "#FFC727",
    "yellow_wall": "#A97F00",
    "on_yellow": "#17150F",
    "red": "#E5534B",
    "on_red": "#FFFFFF",
    "tape": "#111214",
    "tape_ink": "#F3F1EC",
    "noise_alpha": "16",
}

LIGHT: dict[str, str] = {
    "cabinet": "#C6C8C9",
    "rail": "#D2D4D5",
    "foam": "#E8E9EA",
    "foam_hi": "#F2F3F4",
    "cut": "#CFD1D2",
    "cut_hi": "#C4C6C8",
    "wall_dark": "#989B9E",
    "wall_light": "#FAFBFB",
    "edge": "#BDC0C2",
    "shadow": "#4A4E52",
    "ink": "#1B1C1E",
    "ink_dim": "#4F5054",
    "ink_faint": "#55565A",
    "yellow": "#F2B705",
    "yellow_hi": "#FFC52E",
    "yellow_wall": "#B58700",
    "on_yellow": "#17150F",
    "red": "#C93B33",
    "on_red": "#FFFFFF",
    "tape": "#151618",
    "tape_ink": "#F3F1EC",
    "noise_alpha": "13",
}

# Two sizes carry every drawer: names and controls, then metadata and paths
SIZE_MAIN = 14
SIZE_META = 12

LABEL_FAMILY = "Bahnschrift"
LABEL_SEMIBOLD = "Bahnschrift SemiBold"
TAPE_FAMILY = "Bahnschrift SemiBold Condensed"
MONO_FAMILY = "Cascadia Mono"

RADIUS_PANEL = 12
RADIUS_SLOT = 7


def label_font(px: int = SIZE_MAIN, semibold: bool = False) -> QFont:
    font = QFont(LABEL_SEMIBOLD if semibold else LABEL_FAMILY)
    font.setPixelSize(px)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def tape_font(px: int = SIZE_MAIN) -> QFont:
    font = QFont(TAPE_FAMILY)
    font.setPixelSize(px)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(1.0, px * 0.09))
    font.setCapitalization(QFont.Capitalization.AllUppercase)
    return font


def mono_font(px: int = SIZE_META) -> QFont:
    font = QFont(MONO_FAMILY)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFamilies([MONO_FAMILY, "Consolas", "Courier New"])
    font.setPixelSize(px)
    return font


class Theme(QObject):
    """Singleton holding the active palette. Widgets read colors at paint time."""

    changed = Signal()
    _instance: "Theme | None" = None

    def __init__(self):
        super().__init__()
        self._dark = True
        self._noise: dict[bool, QPixmap] = {}

    @classmethod
    def get(cls) -> "Theme":
        if cls._instance is None:
            cls._instance = Theme()
        return cls._instance

    @property
    def is_dark(self) -> bool:
        return self._dark

    @property
    def tokens(self) -> dict[str, str]:
        return DARK if self._dark else LIGHT

    def color(self, name: str, alpha: int | None = None) -> QColor:
        c = QColor(self.tokens[name])
        if alpha is not None:
            c.setAlpha(alpha)
        return c

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(self.tokens))
            for w in app.topLevelWidgets():
                apply_title_bar(w)
        self.changed.emit()

    def noise(self) -> QPixmap:
        """A tile of fine speckle: the cell texture of the foam."""
        if self._dark not in self._noise:
            rng = random.Random(1207)
            size = 128
            img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(0)
            alpha = int(self.tokens["noise_alpha"])
            for y in range(size):
                for x in range(size):
                    r = rng.random()
                    if r < 0.30:
                        img.setPixelColor(x, y, QColor(0, 0, 0, rng.randint(alpha // 2, alpha)))
                    elif r > 0.80:
                        img.setPixelColor(x, y, QColor(255, 255, 255, rng.randint(alpha // 3, alpha // 2 + 1)))
            self._noise[self._dark] = QPixmap.fromImage(img)
        return self._noise[self._dark]


def t(name: str, alpha: int | None = None) -> QColor:
    """Shortcut: a color from the active theme."""
    return Theme.get().color(name, alpha)


def apply_title_bar(widget: QWidget) -> None:
    """Match the native Windows title bar to the theme (immersive dark mode)."""
    if sys.platform != "win32" or not widget.isWindow():
        return
    try:
        import ctypes

        value = ctypes.c_int(1 if Theme.get().is_dark else 0)
        hwnd = int(widget.winId())
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (newer, older builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
    except Exception:
        pass


def build_stylesheet(c: dict[str, str]) -> str:
    """QSS for stock widgets: inputs are cut-outs in the foam, menus are foam sheets."""
    return f"""
* {{
    color: {c['ink']};
    selection-background-color: {c['yellow']};
    selection-color: {c['on_yellow']};
    outline: 0;
}}
QMainWindow, QDialog, #FlutterRunWindow {{ background: {c['cabinet']}; }}
QWidget#Cabinet {{ background: {c['cabinet']}; }}
QWidget#Rail {{ background: {c['rail']}; }}
QLabel {{ background: transparent; }}
QLabel[role="dim"] {{ color: {c['ink_dim']}; font-size: {SIZE_META}px; }}
QLabel[role="caps"] {{ color: {c['ink_dim']}; font-size: {SIZE_META}px; letter-spacing: 1px; }}
QLabel[role="mono"] {{ color: {c['ink_dim']}; font-family: "{MONO_FAMILY}"; font-size: {SIZE_META}px; }}
QLabel[role="title"] {{ font-family: "{LABEL_SEMIBOLD}"; }}
QLabel[role="error"] {{ color: {c['red']}; font-size: {SIZE_META}px; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QListWidget#Plain {{
    background: {c['cut']};
    border: 1px solid {c['cut']};
    border-top: 1px solid {c['wall_dark']};
    border-bottom: 1px solid {c['wall_light']};
    border-radius: {RADIUS_SLOT}px;
    padding: 6px 10px;
    color: {c['ink']};
}}
QLineEdit:hover, QComboBox:hover {{ background: {c['cut_hi']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {c['yellow']};
}}
QLineEdit:disabled, QComboBox:disabled {{ color: {c['ink_faint']}; }}
QLineEdit[mono="true"], QPlainTextEdit[mono="true"] {{ font-family: "{MONO_FAMILY}"; font-size: {SIZE_META + 1}px; }}
QPlainTextEdit, QTextEdit {{ padding: 8px; }}

QComboBox {{ padding-right: 28px; min-height: 20px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background: {c['foam']};
    border: 1px solid {c['edge']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {c['yellow']};
    selection-color: {c['on_yellow']};
    outline: 0;
}}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 0 8px; border-radius: 5px; }}

QPushButton {{
    background: {c['cut']};
    border: none;
    border-top: 1px solid {c['wall_dark']};
    border-bottom: 1px solid {c['wall_light']};
    border-radius: {RADIUS_SLOT}px;
    padding: 7px 16px;
    min-width: 64px;
}}
QPushButton:hover {{ background: {c['cut_hi']}; }}
QPushButton:pressed {{ background: {c['yellow']}; color: {c['on_yellow']}; }}
QPushButton:default {{ background: {c['yellow']}; color: {c['on_yellow']}; border-top-color: {c['yellow_wall']}; }}
QPushButton:default:hover {{ background: {c['yellow_hi']}; }}
QPushButton:focus {{ border: 1px solid {c['yellow']}; }}
QPushButton[slot="true"] {{ min-width: 0; padding: 0; border: none; background: transparent; }}

QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    background: {c['cut']};
    border: 1px solid {c['wall_dark']};
    border-bottom-color: {c['wall_light']};
    border-radius: 4px;
}}
QCheckBox::indicator:hover {{ background: {c['cut_hi']}; }}
QCheckBox::indicator:checked {{ background: {c['yellow']}; border-color: {c['yellow_wall']}; }}
QCheckBox:focus {{ color: {c['yellow']}; }}

QMenu {{
    background: {c['foam']};
    border: 1px solid {c['edge']};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 6px; background: transparent; }}
QMenu::item:selected {{ background: {c['yellow']}; color: {c['on_yellow']}; }}
QMenu::item:disabled {{ color: {c['ink_faint']}; }}
QMenu::separator {{ height: 1px; background: {c['edge']}; margin: 5px 8px; }}
QMenu::icon {{ padding-left: 8px; }}

QToolTip {{
    background: {c['tape']};
    color: {c['tape_ink']};
    border: 1px solid {c['tape']};
    border-radius: 5px;
    padding: 5px 8px;
    font-size: {SIZE_META}px;
}}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {c['edge']}; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {c['ink_faint']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {c['edge']}; border-radius: 3px; min-width: 32px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background: {c['cabinet']}; }}
QSplitter::handle:hover {{ background: {c['edge']}; }}

QMessageBox, QInputDialog {{ background: {c['cabinet']}; }}
QMessageBox QLabel {{ min-width: 280px; }}

QListWidget#Plain::item {{ padding: 6px 8px; border-radius: 5px; }}
QListWidget#Plain::item:selected {{ background: {c['yellow']}; color: {c['on_yellow']}; }}
"""
