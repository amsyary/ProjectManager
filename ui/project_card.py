"""The rail of drawer fronts: one per project, most-opened first."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QModelIndex, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from models.project import Project
from ui import icons
from ui.icon_loader import for_theme, load_icon
from ui.theme import SIZE_MAIN, SIZE_META, label_font, t
from ui.widgets import paint_cut, paint_foam

ROW_H = 64
ROLE_PROJECT = Qt.ItemDataRole.UserRole
ROLE_RUNNING = Qt.ItemDataRole.UserRole + 1


class _DrawerDelegate(QStyledItemDelegate):
    """Paints a drawer front: icon pocket, name, folder count, and the pull handle."""

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), ROW_H)

    def paint(self, p: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        project: Project = index.data(ROLE_PROJECT)
        running: bool = bool(index.data(ROLE_RUNNING))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        focused = bool(option.state & QStyle.StateFlag.State_HasFocus)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        r = QRectF(option.rect).adjusted(8, 3, -8, -5)
        if selected:
            r.translate(4, 0)  # The open drawer sits pulled out of the rail
        if selected or hovered:
            paint_foam(p, r, 9, t("foam_hi") if selected else t("foam"), shadow=selected)

        # Icon pocket
        well = QRectF(r.left() + 10, r.top() + (r.height() - 40) / 2, 40, 40)
        paint_cut(p, well, 9, t("cut"))
        pm = for_theme(load_icon(project.icon_path, 28))
        if pm is not None:
            w = pm.width() / pm.devicePixelRatio()
            h = pm.height() / pm.devicePixelRatio()
            p.drawPixmap(QRectF(well.center().x() - w / 2, well.center().y() - h / 2, w, h), pm, QRectF(pm.rect()))
        else:
            ip = icons.pixmap("drawer", t("ink_faint"), 18)
            p.drawPixmap(QPointF(well.center().x() - 9, well.center().y() - 9), ip)

        # Name and contents
        text_x = well.right() + 12
        right_pad = 26 if running else 12
        text_w = r.right() - text_x - right_pad
        name_font = label_font(SIZE_MAIN, semibold=selected)
        p.setFont(name_font)
        p.setPen(t("ink"))
        fm = QFontMetrics(name_font)
        p.drawText(QRectF(text_x, r.top() + 12, text_w, fm.height()), Qt.AlignmentFlag.AlignLeft,
                   fm.elidedText(project.name, Qt.TextElideMode.ElideRight, int(text_w)))
        meta_font = label_font(SIZE_META)
        p.setFont(meta_font)
        p.setPen(t("ink_dim"))
        n = len(project.sub_projects)
        meta = f"{n} folder{'s' if n != 1 else ''}"
        if project.open_count:
            meta += f"  ·  opened {project.open_count}×"
        p.drawText(QRectF(text_x, r.top() + 14 + fm.height(), text_w, 18), Qt.AlignmentFlag.AlignLeft,
                   QFontMetrics(meta_font).elidedText(meta, Qt.TextElideMode.ElideRight, int(text_w)))

        # Pull handle along the drawer's lower edge; yellow when this drawer is open
        handle_color = t("yellow") if selected else (t("edge") if hovered else t("edge", 0))
        if handle_color.alpha():
            p.setPen(QPen(handle_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(text_x, r.bottom() - 6), QPointF(text_x + min(64, text_w), r.bottom() - 6))

        # A tool is out: something in this drawer is running
        if running:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(t("yellow"))
            p.drawEllipse(QPointF(r.right() - 14, r.center().y()), 4.5, 4.5)

        if focused and selected:
            p.setPen(QPen(t("yellow"), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-1.5, -1.5, 1.5, 1.5), 10, 10)
        p.restore()


class ProjectRail(QListWidget):
    """Projects as drawer fronts. Emits project_selected; right-click offers Edit / Delete."""

    project_selected = Signal(object)
    edit_requested = Signal(object)
    delete_requested = Signal(object)
    open_all_requested = Signal(object)
    typed = Signal(str)  # Printable keys go to the search field
    entered = Signal()  # Plain Enter: hand focus to the open drawer

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_DrawerDelegate(self))
        self.setMouseTracking(True)
        self.setFrameShape(QListWidget.Shape.NoFrame)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QListWidget { background: transparent; border: none; } QListWidget::item { background: transparent; }")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.currentItemChanged.connect(self._current_changed)
        self.itemDoubleClicked.connect(lambda item: self.edit_requested.emit(item.data(ROLE_PROJECT)))
        self._running_check: Optional[Callable[[Project], bool]] = None

    def set_running_check(self, check: Callable[[Project], bool]) -> None:
        self._running_check = check

    def set_projects(self, projects: list[Project], selected_id: Optional[str]) -> None:
        self.blockSignals(True)
        self.clear()
        for project in projects:
            item = QListWidgetItem()
            item.setData(ROLE_PROJECT, project)
            item.setData(ROLE_RUNNING, bool(self._running_check and self._running_check(project)))
            item.setSizeHint(QSize(0, ROW_H))
            item.setToolTip(project.main_project_folder or project.name)
            self.addItem(item)
            if project.id == selected_id:
                self.setCurrentItem(item)
        self.blockSignals(False)

    def refresh_running(self) -> None:
        if not self._running_check:
            return
        for i in range(self.count()):
            item = self.item(i)
            running = bool(self._running_check(item.data(ROLE_PROJECT)))
            if bool(item.data(ROLE_RUNNING)) != running:
                item.setData(ROLE_RUNNING, running)

    def current_project(self) -> Optional[Project]:
        item = self.currentItem()
        return item.data(ROLE_PROJECT) if item else None

    def step(self, delta: int) -> None:
        if not self.count():
            return
        row = self.currentRow()
        row = 0 if row < 0 else max(0, min(self.count() - 1, row + delta))
        self.setCurrentRow(row)

    def _current_changed(self, current: Optional[QListWidgetItem], _previous) -> None:
        self.project_selected.emit(current.data(ROLE_PROJECT) if current else None)

    def keyPressEvent(self, event) -> None:
        project = self.current_project()
        if project and event.key() == Qt.Key.Key_Delete:
            self.delete_requested.emit(project)
        elif project and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.open_all_requested.emit(project)
        elif project and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.entered.emit()
        elif event.text().isprintable() and event.text().strip() and not (
            event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        ):
            self.typed.emit(event.text())
        else:
            super().keyPressEvent(event)

    def _context_menu(self, pos) -> None:
        from ui.widgets import Menu

        item = self.itemAt(pos)
        if item is None:
            return
        project = item.data(ROLE_PROJECT)
        menu = Menu(self)
        menu.add("Edit project", lambda: self.edit_requested.emit(project), icon_name="edit")
        menu.add("Delete project", lambda: self.delete_requested.emit(project), icon_name="trash")
        menu.exec(self.viewport().mapToGlobal(pos))
