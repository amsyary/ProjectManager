"""The shadow-board kit: foam panels, tool cut-outs, Dymo tape, recessed icon wells."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPointF, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QFontMetrics, QKeyEvent, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLayout, QLineEdit, QMenu, QPushButton, QSizePolicy, QWidget,
)

from ui import icons
from ui.theme import RADIUS_PANEL, RADIUS_SLOT, SIZE_MAIN, SIZE_META, Theme, label_font, mono_font, t, tape_font


def _rounded(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def paint_cut(p: QPainter, rect: QRectF, radius: float, floor: QColor, wall: Optional[QColor] = None) -> None:
    """A cut-out in the foam: flat floor, shadowed upper wall, lit lower lip."""
    path = _rounded(rect, radius)
    p.fillPath(path, floor)
    p.save()
    p.setClipPath(path)
    shade = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + 6))
    wall_color = QColor(wall or t("wall_dark"))
    wall_color.setAlpha(150 if Theme.get().is_dark else 110)
    shade.setColorAt(0, wall_color)
    wall_color.setAlpha(0)
    shade.setColorAt(1, wall_color)
    p.fillRect(QRectF(rect.left(), rect.top(), rect.width(), 6), shade)
    lip = t("wall_light", 120 if Theme.get().is_dark else 200)
    p.setPen(QPen(lip, 1))
    p.drawLine(QPointF(rect.left() + radius, rect.bottom() - 0.5), QPointF(rect.right() - radius, rect.bottom() - 0.5))
    p.restore()


def paint_foam(p: QPainter, rect: QRectF, radius: float, fill: QColor, shadow: bool = True) -> None:
    """A slab of foam: soft offset shadow, matte fill with cell texture, hairline edge."""
    if shadow:
        base = t("shadow")
        for offset, alpha in ((1, 34), (2, 18), (4, 10)):
            base.setAlpha(alpha if Theme.get().is_dark else alpha // 2)
            p.fillPath(_rounded(rect.adjusted(0, offset, 0, offset), radius), base)
    path = _rounded(rect, radius)
    p.fillPath(path, fill)
    p.fillPath(path, QBrush(Theme.get().noise()))
    p.setPen(QPen(t("edge"), 1))
    p.drawPath(_rounded(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius))
    top = QColor(255, 255, 255, 10 if Theme.get().is_dark else 150)
    p.setPen(QPen(top, 1))
    p.drawLine(QPointF(rect.left() + radius, rect.top() + 1.5), QPointF(rect.right() - radius, rect.top() + 1.5))


class FoamPanel(QFrame):
    """A raised slab of foam that holds a layout."""

    def __init__(self, parent: Optional[QWidget] = None, radius: int = RADIUS_PANEL):
        super().__init__(parent)
        self._radius = radius
        self._raised = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)  # Slabs never stretch tall

    def set_raised(self, raised: bool) -> None:
        self._raised = raised
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -5)
        paint_foam(p, rect, self._radius, t("foam_hi") if self._raised else t("foam"))


class ToolSlot(QPushButton):
    """A tool sitting in its own cut-out. Yellow floor = primary, pressed, checked or 'tool is out'."""

    def __init__(
        self, text: str = "", icon_name: Optional[str] = None, parent: Optional[QWidget] = None,
        variant: str = "normal", arrow: bool = False, compact: bool = False, tooltip: str = "",
    ):
        super().__init__(text, parent)
        self._icon_name = icon_name
        self._variant = variant  # normal | primary | danger | quiet
        self._arrow = arrow
        self._compact = compact
        self._active = False
        self._out = False  # The tool is out of its slot: something is running
        self._ghost = False  # Disabled shows as an empty dashed cut-out
        self._reserved: list[tuple[str, bool]] = []  # Labels whose width the slot always keeps
        self._hover = 0.0
        self.setAutoDefault(False)  # Enter belongs to the dialog's default button
        self.setProperty("slot", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFont(label_font(SIZE_META, semibold=True))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if tooltip:
            self.setToolTip(tooltip)
        self._anim = QVariantAnimation(self, duration=140, easingCurve=QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_hover)

    # -- state --

    def set_active(self, active: bool) -> None:
        if active != self._active:
            self._active = active
            self.update()

    def set_out(self, out: bool) -> None:
        """Paint as an empty slot with the yellow under-layer showing: the tool is in use."""
        if out != self._out:
            self._out = out
            self.updateGeometry()
            self.update()

    def reserve(self, *labels: str, out: bool = False) -> None:
        """Keep room for these labels so the slot never changes width when its label does."""
        self._reserved += [(label, out) for label in labels]
        self.updateGeometry()

    def set_ghost_when_disabled(self, ghost: bool) -> None:
        self._ghost = ghost
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers():
            self.animateClick()
            return
        super().keyPressEvent(event)

    def _text_font(self):
        return mono_font(SIZE_META) if self._out else self.font()

    def set_icon_name(self, name: Optional[str]) -> None:
        self._icon_name = name
        self.updateGeometry()
        self.update()

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self.update()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt override)
        super().setText(text)
        self.updateGeometry()

    def _set_hover(self, value) -> None:
        self._hover = float(value)
        self.update()

    def enterEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)

    # -- geometry --

    def _label(self) -> str:
        return self.text() if self._out else self.text().upper()

    def sizeHint(self) -> QSize:
        width = self._width_for(self._label(), self._text_font())
        for label, out in self._reserved:
            font = mono_font(SIZE_META) if out else self.font()
            width = max(width, self._width_for(label if out else label.upper(), font))
        return QSize(width, 30 if self._compact else 34)

    def _width_for(self, text: str, font) -> int:
        fm = QFontMetrics(font)
        height = 30 if self._compact else 34
        width = 4  # Focus ring room
        pad = 10 if self._compact else 12
        if self._icon_name:
            width += 16
        if text:
            width += fm.horizontalAdvance(text) + int(len(text) * 0.6)
            if self._icon_name:
                width += 7
        if self._arrow:
            width += 14
        width += pad * 2 if text else 2 * (height - 4 - 16) // 2
        if not text and not self._arrow:
            width = height
        return width

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # -- painting --

    def _colors(self) -> tuple[QColor, QColor, Optional[QColor]]:
        """(floor, ink, wall) for the current state."""
        enabled = self.isEnabled()
        down = self.isDown()
        lit = self._active or self.isChecked() or down
        if not enabled:
            return t("cut"), t("ink_faint", 150), None
        if self._variant == "primary" or lit:
            floor = QColor(t("yellow_hi") if (self._hover > 0.5 and not down) else t("yellow"))
            return floor, t("on_yellow"), t("yellow_wall")
        if self._variant == "danger" and self._hover > 0.5:
            return t("red"), t("on_red"), None
        floor = _mix(t("cut"), t("cut_hi"), self._hover)
        ink = t("ink") if self._variant != "quiet" else _mix(t("ink_dim"), t("ink"), self._hover)
        return floor, ink, None

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(self.rect())
        slot = outer.adjusted(2, 2, -2, -2)
        floor, ink, wall = self._colors()
        if self._out and self.isEnabled():
            # The under-layer shows where the tool was lifted out; its outline stays cut in the floor
            paint_cut(p, slot, RADIUS_SLOT, t("yellow"), t("yellow_wall"))
            pen = QPen(t("yellow_wall"), 1.3, Qt.PenStyle.DashLine)
            pen.setDashPattern([3, 2.5])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(slot.adjusted(3.5, 3.5, -3.5, -3.5), RADIUS_SLOT - 3, RADIUS_SLOT - 3)
            ink = t("on_yellow")
        elif self._ghost and not self.isEnabled():
            pen = QPen(t("ink_faint", 110), 1.2, Qt.PenStyle.DashLine)
            pen.setDashPattern([3, 3])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(slot.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS_SLOT, RADIUS_SLOT)
        elif self._variant == "quiet" and self._hover == 0 and not (self._active or self.isChecked() or self.isDown()):
            pass  # Quiet tools show their slot only on hover
        else:
            paint_cut(p, slot, RADIUS_SLOT, floor, wall)

        lift = 0.0 if self.isDown() else -1.0 * self._hover
        if self.isDown():
            lift = 0.5
        text = self._label()
        fm = QFontMetrics(self._text_font())
        spacing = 0.0 if self._out else 0.6
        text_w = fm.horizontalAdvance(text) + int(len(text) * spacing) if text else 0
        content_w = (16 if self._icon_name else 0) + (7 if self._icon_name and text else 0) + text_w
        if self._arrow:
            content_w += 14
        x = slot.left() + (slot.width() - content_w) / 2
        cy = slot.center().y() + lift

        if self._icon_name:
            pm = icons.pixmap(self._icon_name, ink, 16)
            p.drawPixmap(QPointF(x, cy - 8), pm)
            x += 16 + (7 if text else 0)
        if text:
            font = self._text_font()
            font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, spacing)
            p.setFont(font)
            p.setPen(ink)
            p.drawText(QRectF(x, slot.top() + lift, text_w + 2, slot.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            x += text_w
        if self._arrow:
            pm = icons.pixmap("chevron", ink, 12)
            p.drawPixmap(QPointF(x + 2, cy - 6), pm)

        if self.hasFocus():
            p.setPen(QPen(t("yellow"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(outer.adjusted(1, 1, -1, -1), RADIUS_SLOT + 1, RADIUS_SLOT + 1)


def _mix(a: QColor, b: QColor, f: float) -> QColor:
    f = max(0.0, min(1.0, f))
    return QColor(
        int(a.red() + (b.red() - a.red()) * f),
        int(a.green() + (b.green() - a.green()) * f),
        int(a.blue() + (b.blue() - a.blue()) * f),
        int(a.alpha() + (b.alpha() - a.alpha()) * f),
    )


class DymoLabel(QWidget):
    """Label-maker tape: white capitals reversed out of black tape."""

    def __init__(self, text: str = "", px: int = SIZE_MAIN, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._text = text
        self._px = px
        self.setFont(tape_font(px))
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self._text.upper()) + 22, self._px + 14)

    def minimumSizeHint(self) -> QSize:
        return QSize(min(self.sizeHint().width(), 80), self._px + 14)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(0, 0, min(self.width(), self.sizeHint().width()), self.height()).adjusted(0.5, 0.5, -0.5, -1.5)
        # Tape body with a faint drop so it sits on the foam
        p.fillPath(_rounded(rect.adjusted(0, 1.5, 0, 1.5), 3), QColor(0, 0, 0, 70))
        path = _rounded(rect, 3)
        p.fillPath(path, t("tape"))
        p.fillPath(path, QBrush(Theme.get().noise()))
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawLine(QPointF(rect.left() + 3, rect.top() + 1), QPointF(rect.right() - 3, rect.top() + 1))

        fm = QFontMetrics(self.font())
        text = fm.elidedText(self._text.upper(), Qt.TextElideMode.ElideRight, int(rect.width()) - 20)
        p.setFont(self.font())
        text_rect = rect.adjusted(11, 0, -9, 0)
        flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        p.setPen(t("tape_ink"))
        p.drawText(text_rect, flags, text)


class IconWell(QWidget):
    """A recessed square pocket holding a project or type image."""

    def __init__(self, size: int = 40, parent: Optional[QWidget] = None, fallback: str = "drawer"):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._fallback = fallback
        self.setFixedSize(size, size)

    def set_pixmap(self, pm: Optional[QPixmap]) -> None:
        self._pixmap = pm
        self.update()

    def set_fallback(self, name: str) -> None:
        self._fallback = name
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_cut(p, rect, max(6.0, self.width() * 0.22), t("cut"))
        inner = self.width() * 0.66
        target = QRectF((self.width() - inner) / 2, (self.height() - inner) / 2, inner, inner)
        if self._pixmap is not None:
            from ui.icon_loader import for_theme

            pm = for_theme(self._pixmap)
            w = pm.width() / pm.devicePixelRatio()
            h = pm.height() / pm.devicePixelRatio()
            scale = min(inner / w, inner / h)
            dw, dh = w * scale, h * scale
            p.drawPixmap(QRectF((self.width() - dw) / 2, (self.height() - dh) / 2 + 0.5, dw, dh), pm, QRectF(pm.rect()))
        else:
            size = int(inner * 0.62)
            pm = icons.pixmap(self._fallback, t("ink_faint"), size)
            p.drawPixmap(QPointF((self.width() - size) / 2, (self.height() - size) / 2), pm)


class FlowLayout(QLayout):
    """Lays children out in rows that wrap, aligned left or right."""

    def __init__(self, parent: Optional[QWidget] = None, spacing: int = 4, align_right: bool = False):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self._right = align_right
        self.setContentsMargins(0, 0, 0, 0)

    def set_align_right(self, right: bool) -> None:
        if right != self._right:
            self._right = right
            self.invalidate()

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return False  # The owner sets its minimum height from heightForWidth() on resize

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        w = sum(i.sizeHint().width() for i in self._visible()) + self._spacing * max(0, len(self._visible()) - 1)
        h = max((i.sizeHint().height() for i in self._visible()), default=0)
        return QSize(w, h)

    def minimumSize(self) -> QSize:  # noqa: N802
        w = max((i.minimumSize().width() for i in self._visible()), default=0)
        h = max((i.minimumSize().height() for i in self._visible()), default=0)
        return QSize(w, h)

    def _visible(self) -> list:
        return [i for i in self._items if not (i.widget() and i.widget().isHidden())]

    def _do_layout(self, rect: QRect, test: bool) -> int:
        lines: list[list] = [[]]
        line_w = 0
        for item in self._visible():
            w = item.sizeHint().width()
            if lines[-1] and line_w + self._spacing + w > rect.width():
                lines.append([])
                line_w = 0
            line_w += (self._spacing if lines[-1] else 0) + w
            lines[-1].append(item)
        y = rect.y()
        for line in lines:
            if not line:
                continue
            h = max(i.sizeHint().height() for i in line)
            total = sum(i.sizeHint().width() for i in line) + self._spacing * (len(line) - 1)
            x = rect.right() - total + 1 if self._right else rect.x()
            if not test:
                for item in line:
                    size = item.sizeHint()
                    item.setGeometry(QRect(QPoint(x, y + (h - size.height()) // 2), size))
                    x += size.width() + self._spacing
            y += h + self._spacing
        return y - rect.y() - self._spacing if y > rect.y() else 0


class SearchField(QLineEdit):
    """Search slot: Up/Down/Enter drive the list beside it; Esc clears."""

    navigate = Signal(int)
    accepted = Signal()

    def __init__(self, placeholder: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self._action = self.addAction(icons.icon("search", t("ink_faint"), 16), QLineEdit.ActionPosition.LeadingPosition)
        Theme.get().changed.connect(self._retheme)

    def _retheme(self) -> None:
        self._action.setIcon(icons.icon("search", t("ink_faint"), 16))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Down:
            self.navigate.emit(1)
        elif key == Qt.Key.Key_Up:
            self.navigate.emit(-1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers():
            self.accepted.emit()
        elif key == Qt.Key.Key_Escape and self.text():
            self.clear()
        else:
            super().keyPressEvent(event)


class Combo(QComboBox):
    """A combo box cut into the foam, with a drawn chevron and a rounded popup."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        popup = self.view().window()
        popup.setWindowFlags(popup.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        color = t("ink_dim") if self.isEnabled() else t("ink_faint")
        p.drawPixmap(QPointF(self.width() - 22, (self.height() - 12) / 2), icons.pixmap("chevron", color, 12))


class Menu(QMenu):
    """Foam sheet menu with rounded corners."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setToolTipsVisible(True)

    def add(self, text: str, slot=None, enabled: bool = True, icon_name: Optional[str] = None, tip: str = ""):
        action = self.addAction(text)
        if icon_name:
            action.setIcon(icons.icon(icon_name, t("ink_dim"), 16))
        if slot is not None:
            action.triggered.connect(slot)
        action.setEnabled(enabled)
        if tip:
            action.setToolTip(tip)
        return action

    def popup_below(self, widget: QWidget) -> None:
        self.exec(widget.mapToGlobal(QPoint(2, widget.height() + 2)))


class ScanBar(QWidget):
    """A thin yellow sweep that runs while flutter is building or stopping."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._pos = 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1400, loopCount=-1)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.valueChanged.connect(self._tick)
        self.hide()

    def _tick(self, value) -> None:
        self._pos = float(value)
        self.update()

    def start(self) -> None:
        if not self.isVisible():
            self.show()
            self._anim.start()

    def stop(self) -> None:
        self._anim.stop()
        self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        p.fillPath(_rounded(rect, 2), t("cut"))
        seg = rect.width() * 0.28
        x = (rect.width() + seg) * self._pos - seg
        p.save()
        p.setClipPath(_rounded(rect, 2))
        p.fillRect(QRectF(x, 0, seg, rect.height()), t("yellow"))
        p.restore()


class StatusLamp(QWidget):
    """A small indicator: idle (hollow), busy (breathing yellow), running (yellow), error (red)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._state = "idle"
        self._level = 1.0
        self._anim = QVariantAnimation(self, startValue=0.35, endValue=1.0, duration=700, loopCount=-1)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setDirection(QVariantAnimation.Direction.Forward)
        self._anim.valueChanged.connect(self._breathe)

    def _breathe(self, value) -> None:
        self._level = float(value)
        self.update()

    def set_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        if state == "busy":
            self._anim.start()
        else:
            self._anim.stop()
            self._level = 1.0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.5, 1.5, 9, 9)
        if self._state == "idle":
            p.setPen(QPen(t("ink_faint"), 1.5))
            p.drawEllipse(rect)
            return
        color = t("red") if self._state == "error" else t("yellow")
        if self._state == "busy":
            color.setAlphaF(self._level)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(rect)


def caps_label_text(text: str) -> str:
    return text.upper()


def hline(parent: Optional[QWidget] = None) -> QFrame:
    """A hairline rule in the foam's edge color."""
    line = QFrame(parent)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {Theme.get().tokens['edge']};")
    return line
