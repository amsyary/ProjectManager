"""A read-only log that colors `flutter run` output like VS Code: ANSI codes first, then by line."""

from __future__ import annotations

import re
from collections import deque
from typing import Iterable, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from ui.theme import SIZE_META, Theme, mono_font, t

MAX_LOG_LINES = 5000

Line = tuple[str, str]  # (text, kind): kind is "log", "error" or "note"

_CSI = re.compile(r"\x1b\[([0-9;:?]*)([@-~])")
_OTHER_ESC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")

# Lines without ANSI colors get one by what they say
_ERROR = re.compile(
    r"^E/|^\[E\]|\b(?:Exception|Error|FAILURE|FAILED|Failed)\b|══╡ EXCEPTION|\[ERROR\]|\bERROR\b|^\s*Unhandled\b",
)
_WARN = re.compile(r"^W/|^\[W\]|\b(?:Warning|WARNING|WARN|Deprecated|deprecated)\b")
_OK = re.compile(
    r"Reloaded \d+ of \d+|Restarted application|^\s*✓|Built build[\\/]|Hot (?:reload|restart) done|"
    r"Application finished|Flutter run key commands",
)
_INFO = re.compile(r"^(?:Launching |Running Gradle task|Syncing files|Installing |Waiting for |Building )")
_FRAME = re.compile(r"^\s*#\d+\s")
_PREFIX = re.compile(r"^[VDIWEF]/[\w.$\-]+\s*\(\s*\d+\):\s?|^flutter: ")  # logcat tag or "flutter: "
_LINK = re.compile(r"https?://[^\s'\"<>)\]]+|package:[\w/.\-]+\.dart(?::\d+(?::\d+)?)?|\b[\w/\\.\-]+\.dart:\d+(?::\d+)?")


def _xterm(n: int) -> Optional[QColor]:
    """One of the 256 xterm colors."""
    if n < 16:
        return QColor(Theme.get().ansi[n])
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return QColor(steps[n // 36], steps[(n // 6) % 6], steps[n % 6])
    if n < 256:
        level = 8 + (n - 232) * 10
        return QColor(level, level, level)
    return None


class _Style:
    """The SGR state while walking a line."""

    __slots__ = ("fg", "bg", "bold", "dim", "italic", "underline")

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.fg: Optional[QColor] = None
        self.bg: Optional[QColor] = None
        self.bold = self.dim = self.italic = self.underline = False

    def apply(self, params: str) -> None:
        codes = [int(p) if p.isdigit() else 0 for p in re.split(r"[;:]", params)] if params else [0]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                self.reset()
            elif c == 1:
                self.bold = True
            elif c == 2:
                self.dim = True
            elif c == 3:
                self.italic = True
            elif c == 4:
                self.underline = True
            elif c == 22:
                self.bold = self.dim = False
            elif c == 23:
                self.italic = False
            elif c == 24:
                self.underline = False
            elif 30 <= c <= 37:
                self.fg = _xterm(c - 30)
            elif 90 <= c <= 97:
                self.fg = _xterm(c - 90 + 8)
            elif c == 39:
                self.fg = None
            elif 40 <= c <= 47:
                self.bg = _xterm(c - 40)
            elif 100 <= c <= 107:
                self.bg = _xterm(c - 100 + 8)
            elif c == 49:
                self.bg = None
            elif c in (38, 48) and i + 1 < len(codes):
                color = None
                if codes[i + 1] == 5 and i + 2 < len(codes):
                    color = _xterm(codes[i + 2])
                    i += 2
                elif codes[i + 1] == 2 and i + 4 < len(codes):
                    color = QColor(*(max(0, min(255, v)) for v in codes[i + 2:i + 5]))
                    i += 4
                if c == 38:
                    self.fg = color
                else:
                    self.bg = color
            i += 1


def ansi_segments(text: str) -> list[tuple[str, Optional[_Style]]]:
    """Split text into (piece, style) runs; style is None where no ANSI code is in effect."""
    text = _OTHER_ESC.sub("", text)
    if "\x1b" not in text:
        return [(text, None)]
    out: list[tuple[str, Optional[_Style]]] = []
    style = _Style()
    styled = False
    pos = 0
    for m in _CSI.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], _copy(style) if styled else None))
        if m.group(2) == "m":
            style.apply(m.group(1))
            styled = True
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], _copy(style) if styled else None))
    return [(piece.replace("\x1b", ""), s) for piece, s in out if piece]


def _luminance(c: QColor) -> float:
    def channel(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(c.redF()) + 0.7152 * channel(c.greenF()) + 0.0722 * channel(c.blueF())


def _contrast(a: QColor, b: QColor) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _copy(style: _Style) -> _Style:
    c = _Style()
    for name in _Style.__slots__:
        setattr(c, name, getattr(style, name))
    return c


def strip_ansi(text: str) -> str:
    return "".join(piece for piece, _ in ansi_segments(text))


def line_color(text: str, kind: str) -> Optional[QColor]:
    """The color a line gets when it carries no ANSI color: errors red, warnings amber, ..."""
    log = Theme.get().log
    if kind == "error" or _ERROR.search(text):
        return QColor(log["error"])
    if kind == "note":
        return t("ink_dim")
    if _WARN.search(text):
        return QColor(log["warn"])
    if _OK.search(text):
        return QColor(log["ok"])
    if _FRAME.match(text):
        return t("ink_faint")
    if _INFO.match(text):
        return QColor(log["info"])
    return None


class LogView(QPlainTextEdit):
    """Keeps the lines it shows, so it can repaint them in the other theme's colors.

    Links (http, package:, file.dart:line) are underlined; Ctrl+click opens web links.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._lines: deque[Line] = deque(maxlen=MAX_LOG_LINES)
        self.setReadOnly(True)
        self.setMaximumBlockCount(MAX_LOG_LINES)
        self.setFont(mono_font(SIZE_META + 1))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setUndoRedoEnabled(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        Theme.get().changed.connect(self._retheme)

    # -- content --

    def set_lines(self, lines: Iterable[Line]) -> None:
        self._lines.clear()
        super().clear()
        self.append_lines(lines)

    def append_lines(self, lines: Iterable[Line]) -> None:
        lines = list(lines)
        if not lines:
            return
        bar = self.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 2
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for text, kind in lines:
            if self._lines:
                cursor.insertBlock()
            self._lines.append((text, kind))
            self._insert(cursor, text, kind)
        cursor.endEditBlock()
        if at_bottom:
            bar.setValue(bar.maximum())

    def clear(self) -> None:  # noqa: D102 (Qt override)
        self._lines.clear()
        super().clear()

    def _retheme(self) -> None:
        try:
            lines = list(self._lines)
        except RuntimeError:
            return
        value = self.verticalScrollBar().value()
        self.set_lines(lines)
        self.verticalScrollBar().setValue(value)

    # -- painting a line --

    def _insert(self, cursor: QTextCursor, text: str, kind: str) -> None:
        segments = ansi_segments(text)
        plain = "".join(piece for piece, _ in segments)
        base = line_color(plain, kind)
        prefix = _PREFIX.match(plain)
        prefix_end = prefix.end() if prefix else 0
        links = [(m.start(), m.end(), m.group()) for m in _LINK.finditer(plain)]
        pos = 0
        for piece, style in segments:
            # Cut the piece where the logcat prefix and links begin and end
            cuts = {0, len(piece)}
            for a, b, _ in links:
                cuts.update((a - pos, b - pos))
            cuts.add(prefix_end - pos)
            edges = sorted(c for c in cuts if 0 <= c <= len(piece))
            for a, b in zip(edges, edges[1:]):
                part = piece[a:b]
                if not part:
                    continue
                start = pos + a
                link = next((url for la, lb, url in links if la <= start < lb), None)
                cursor.insertText(part, self._format(style, base, kind, start < prefix_end, link))
            pos += len(piece)

    def _format(self, style: Optional[_Style], base: Optional[QColor], kind: str, in_prefix: bool,
                link: Optional[str]) -> QTextCharFormat:
        fmt = QTextCharFormat()
        color = style.fg if style and style.fg else None
        if color is None:
            if link:
                color = QColor(Theme.get().log["link"])
            elif in_prefix:
                color = t("ink_faint")
            else:
                color = base
        if style and style.bg:
            fmt.setBackground(style.bg)
            # A badge like "white on blue": keep the text readable on its own background in both themes
            if color is None or _contrast(color, style.bg) < 3:
                color = QColor("#FFFFFF") if _luminance(style.bg) < 0.3 else QColor("#141414")
        if color is not None:
            if style and style.dim:
                color = QColor(color)
                color.setAlpha(170)
            fmt.setForeground(color)
        if style and style.bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if (style and style.italic) or kind == "note":
            fmt.setFontItalic(True)
        if (style and style.underline) or link:
            fmt.setFontUnderline(True)
        if link and link.startswith("http"):
            fmt.setAnchor(True)
            fmt.setAnchorHref(link)
            fmt.setToolTip("Ctrl+click to open")
        return fmt

    # -- links --

    def mouseReleaseEvent(self, event) -> None:
        href = self.anchorAt(event.position().toPoint())
        if href and event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(href))
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        over = bool(self.anchorAt(event.position().toPoint()))
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.IBeamCursor)
