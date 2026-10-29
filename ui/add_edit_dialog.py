"""Add / edit a project: identity, main folder and its folders (sub-projects)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from models.project import Project, ProjectType, SubProject, SubProjectCommand
from services.project_service import ProjectService
from ui import dialogs
from ui.commands_dialog import CommandsDialog
from ui.icon_loader import for_theme, load_icon, load_type_icon
from ui.theme import RADIUS_SLOT, apply_title_bar, t
from ui.widgets import Combo, FoamPanel, IconWell, ToolSlot, paint_cut

TYPE_ORDER = [
    ProjectType.FLUTTER, ProjectType.ADMIN_DASHBOARD, ProjectType.CLOUD_FUNCTION,
    ProjectType.WEB_VERSION, ProjectType.DOCUMENTATION, ProjectType.GENERAL,
    ProjectType.DATA_TXT, ProjectType.EXECUTE, ProjectType.LINK,
]


def _caps(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("role", "caps")
    return label


def _is_valid_url(s: str) -> bool:
    try:
        result = urlparse(s)
        return all([result.scheme, result.netloc]) and result.scheme in ("http", "https")
    except Exception:
        return False


class _FolderRow(FoamPanel):
    """One folder (sub-project) being edited."""

    def __init__(self, dialog: "ProjectDialog", sp: Optional[SubProject] = None, sp_type: ProjectType = ProjectType.GENERAL):
        super().__init__(radius=10)
        self._dialog = dialog
        self.sp_id = sp.id if sp else None
        self.commands: list[SubProjectCommand] = list(sp.commands) if sp else []

        grid = QGridLayout(self)
        grid.setContentsMargins(14, 12, 12, 16)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.number = QLabel("1")
        self.number.setProperty("role", "dim")
        self.number.setFixedWidth(18)
        grid.addWidget(self.number, 0, 0)

        self.type_box = Combo()
        for pt in TYPE_ORDER:
            pm = for_theme(load_type_icon(pt.value, 18))
            self.type_box.addItem(QIcon(pm) if pm else QIcon(), ProjectType.display_name(pt), pt)
        self.type_box.setIconSize(QSize(18, 18))
        self.type_box.setFixedWidth(220)
        current = sp.type if sp else sp_type
        self.type_box.setCurrentIndex(TYPE_ORDER.index(current) if current in TYPE_ORDER else TYPE_ORDER.index(ProjectType.GENERAL))
        self.type_box.currentIndexChanged.connect(self._type_changed)
        grid.addWidget(self.type_box, 0, 1)

        self.name = QLineEdit((sp.name or "") if sp else "")
        self.name.setPlaceholderText("Name (optional, defaults to the folder name)")
        grid.addWidget(self.name, 0, 2, 1, 3)

        remove = ToolSlot("", "trash", variant="danger", tooltip="Remove this folder from the project")
        remove.clicked.connect(lambda: dialog.remove_row(self))
        grid.addWidget(remove, 0, 5)

        self.path = QLineEdit(sp.directory if sp else "")
        self.path.setProperty("mono", True)
        grid.addWidget(self.path, 1, 1, 1, 2)
        self.browse = ToolSlot("Folder", "folder")
        self.browse.reserve("Folder", "File", "URL")  # Same width for every type: paths line up across rows
        self.browse.clicked.connect(self._browse)
        grid.addWidget(self.browse, 1, 3)
        self.commands_btn = ToolSlot("", "run", tooltip="Terminal commands for this folder, e.g. npm run dev")
        self.commands_btn.clicked.connect(self._edit_commands)
        grid.addWidget(self.commands_btn, 1, 4, 1, 2)
        grid.setColumnStretch(2, 1)
        self._type_changed()
        self._update_commands_btn()

    def sp_type(self) -> ProjectType:
        return self.type_box.currentData()

    def _type_changed(self) -> None:
        pt = self.sp_type()
        if ProjectType.is_link_type(pt):
            self.path.setPlaceholderText("https://example.com")
            self.browse.setText("URL")
            self.browse.set_icon_name("globe")
        elif ProjectType.is_file_type(pt):
            self.path.setPlaceholderText("C:/path/to/file")
            self.browse.setText("File")
            self.browse.set_icon_name("file")
        else:
            self.path.setPlaceholderText("C:/path/to/folder")
            self.browse.setText("Folder")
            self.browse.set_icon_name("folder")
        self.commands_btn.setVisible(not ProjectType.is_link_type(pt))

    def _browse(self) -> None:
        pt = self.sp_type()
        current = self.path.text().strip()
        if pt == ProjectType.LINK:
            url = dialogs.ask_text(self.window(), "Link", "URL to open in the browser:", current or "https://", mono=True)
            if url:
                self.path.setText(url.strip())
            return
        start = current if current and os.path.exists(current) else ""
        if pt == ProjectType.DATA_TXT:
            path, _ = QFileDialog.getOpenFileName(
                self.window(), "Select a file to open in Notepad", start,
                "All files (*.*);;Text files (*.txt *.md *.log *.csv);;"
                "Config files (*.json *.yaml *.yml *.env *.ini *.xml *.toml)",
            )
        elif pt == ProjectType.EXECUTE:
            path, _ = QFileDialog.getOpenFileName(self.window(), "Select a file to open or run", start, "All files (*.*)")
        else:
            path = QFileDialog.getExistingDirectory(self.window(), "Select project folder", start)
        if path:
            self.path.setText(path)

    def _update_commands_btn(self) -> None:
        n = len(self.commands)
        self.commands_btn.setText(f"Commands · {n}" if n else "Add commands")

    def _edit_commands(self) -> None:
        label = self.name.text().strip() or Path(self.path.text().strip()).name or "folder"
        result = CommandsDialog.edit(self.window(), self.commands, f"Commands: {label}")
        if result is not None:
            self.commands = result
            self._update_commands_btn()


class _IconChoice(QPushButton):
    """A default icon in the picker: a pocket that fills yellow on hover."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self._pm = load_icon(str(path), 44)
        self.setFixedSize(68, 68)
        self.setProperty("slot", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(path.stem.replace("_", " "))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        hovered = self.underMouse() or self.hasFocus()
        paint_cut(p, QRectF(self.rect()).adjusted(2, 2, -2, -2), RADIUS_SLOT + 3,
                  t("yellow") if hovered else t("cut"), t("yellow_wall") if hovered else None)
        if self._pm:
            w = self._pm.width() / self._pm.devicePixelRatio()
            h = self._pm.height() / self._pm.devicePixelRatio()
            p.drawPixmap(QRectF((68 - w) / 2, (68 - h) / 2, w, h), self._pm, QRectF(self._pm.rect()))


def pick_default_icon(parent: QWidget) -> Optional[str]:
    """Grid of bundled icons. Returns "default_icon:<file>" or None."""
    default_dir = ProjectService.default_icons_dir()
    icons = sorted(
        f for f in default_dir.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")
    ) if default_dir.exists() else []
    if not icons:
        dialogs.info(parent, "Default icons", "No default icons found.")
        return None
    dlg = QDialog(parent)
    dlg.setWindowTitle("Choose a default icon")
    root = QVBoxLayout(dlg)
    root.setContentsMargins(20, 18, 20, 18)
    root.setSpacing(12)
    hint = QLabel("Click an icon to use it.")
    hint.setProperty("role", "dim")
    root.addWidget(hint)
    grid = QGridLayout()
    grid.setSpacing(6)
    chosen: list[str] = []
    for i, path in enumerate(icons):
        btn = _IconChoice(path)
        btn.clicked.connect(lambda _=False, p=path: (chosen.append(f"default_icon:{p.name}"), dlg.accept()))
        grid.addWidget(btn, i // 6, i % 6)
    root.addLayout(grid)
    cancel = ToolSlot("Cancel")
    cancel.clicked.connect(dlg.reject)
    root.addWidget(cancel, 0, Qt.AlignmentFlag.AlignRight)
    apply_title_bar(dlg)
    dlg.exec()
    return chosen[0] if chosen else None


class ProjectDialog(QDialog):
    """Modal editor for a new or existing project."""

    def __init__(self, parent: Optional[QWidget], project: Optional[Project] = None):
        super().__init__(parent)
        self.project = project
        self.result_project: Optional[Project] = None
        self._rows: list[_FolderRow] = []
        self.setWindowTitle("Edit project" if project else "Add project")
        self.resize(940, 680)
        self.setMinimumSize(760, 520)
        self._build()
        if project:
            self._load(project)
        else:
            self._add_row(focus=False)
        self._name.setFocus()
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_save)

    def showEvent(self, event) -> None:
        apply_title_bar(self)
        super().showEvent(event)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        identity = FoamPanel()
        grid = QGridLayout(identity)
        grid.setContentsMargins(18, 16, 18, 20)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        icon_col = QVBoxLayout()
        icon_col.setSpacing(6)
        self._preview = IconWell(88, fallback="image")
        icon_col.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignHCenter)
        icon_buttons = QHBoxLayout()
        icon_buttons.setSpacing(2)
        browse_icon = ToolSlot("", "image", compact=True, tooltip="Choose an image file")
        browse_icon.clicked.connect(self._browse_icon)
        default_icon = ToolSlot("", "grid", compact=True, tooltip="Choose a default icon")
        default_icon.clicked.connect(self._choose_default_icon)
        clear_icon = ToolSlot("", "close", compact=True, variant="quiet", tooltip="Remove the icon")
        clear_icon.clicked.connect(lambda: self._icon.setText(""))
        for b in (browse_icon, default_icon, clear_icon):
            icon_buttons.addWidget(b)
        icon_col.addLayout(icon_buttons)
        icon_col.addStretch()
        grid.addLayout(icon_col, 0, 0, 3, 1)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Hello Teacher")
        grid.addWidget(_caps("Project name"), 0, 1)
        grid.addWidget(self._name, 0, 2, 1, 2)

        self._icon = QLineEdit()
        self._icon.setProperty("mono", True)
        self._icon.setPlaceholderText("optional: image file or a default icon")
        self._icon.textChanged.connect(self._update_preview)
        grid.addWidget(_caps("Icon"), 1, 1)
        grid.addWidget(self._icon, 1, 2, 1, 2)

        self._main_folder = QLineEdit()
        self._main_folder.setProperty("mono", True)
        self._main_folder.setPlaceholderText("optional: opens in Explorer, terminal, tasks and launch")
        browse_main = ToolSlot("Browse", "folder")
        browse_main.clicked.connect(self._browse_main_folder)
        grid.addWidget(_caps("Main folder"), 2, 1)
        grid.addWidget(self._main_folder, 2, 2)
        grid.addWidget(browse_main, 2, 3)
        grid.setColumnStretch(2, 1)
        root.addWidget(identity)

        head = QHBoxLayout()
        self._folders_label = _caps("Folders")
        head.addWidget(self._folders_label)
        head.addStretch()
        add = ToolSlot("Add folder", "plus")
        add.clicked.connect(lambda: self._add_row(focus=True))
        head.addWidget(add)
        root.addLayout(head)

        self._list = QVBoxLayout()
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(4)
        self._list.addStretch()
        holder = QWidget()
        holder.setLayout(self._list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(holder)
        self._scroll = scroll
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        keys = QLabel("Ctrl+S saves · Esc cancels")
        keys.setProperty("role", "dim")
        footer.addWidget(keys)
        footer.addStretch()
        cancel = ToolSlot("Cancel")
        cancel.clicked.connect(self.reject)
        save = ToolSlot("Save project", "check", variant="primary")
        save.setDefault(True)  # Enter in any field saves
        save.clicked.connect(self._on_save)
        footer.addWidget(cancel)
        footer.addWidget(save)
        root.addLayout(footer)
        self._update_preview()

    def _load(self, project: Project) -> None:
        self._name.setText(project.name)
        self._icon.setText(project.icon_path or "")
        self._main_folder.setText(project.main_project_folder or "")
        for sp in project.sub_projects:
            self._add_row(sp)

    def _add_row(self, sp: Optional[SubProject] = None, focus: bool = False) -> None:
        row = _FolderRow(self, sp)
        self._list.insertWidget(self._list.count() - 1, row)
        self._rows.append(row)
        self._renumber()
        if focus:
            row.path.setFocus()
            self._scroll.ensureWidgetVisible(row)

    def remove_row(self, row: _FolderRow) -> None:
        self._rows.remove(row)
        row.deleteLater()
        self._renumber()

    def _renumber(self) -> None:
        for i, row in enumerate(self._rows, start=1):
            row.number.setText(str(i))
        n = len(self._rows)
        self._folders_label.setText(f"FOLDERS · {n}" if n else "FOLDERS")

    def _update_preview(self) -> None:
        path = self._icon.text().strip() or None
        self._preview.set_pixmap(load_icon(path, 64) if path else None)

    def _browse_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select project icon", "", "Images (*.png *.jpg *.jpeg *.gif *.ico *.bmp);;All files (*.*)")
        if path:
            self._icon.setText(path)

    def _choose_default_icon(self) -> None:
        chosen = pick_default_icon(self)
        if chosen:
            self._icon.setText(chosen)

    def _browse_main_folder(self) -> None:
        current = self._main_folder.text().strip()
        path = QFileDialog.getExistingDirectory(self, "Select main project folder", current if os.path.isdir(current) else "")
        if path:
            self._main_folder.setText(path)

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            dialogs.error(self, "Project name", "Give the project a name.")
            self._name.setFocus()
            return

        sub_projects = []
        for row in self._rows:
            d = row.path.text().strip()
            if not d:
                continue
            pt = row.sp_type()
            if pt == ProjectType.LINK and not _is_valid_url(d):
                dialogs.error(
                    self, "Invalid URL",
                    "Enter a full URL (e.g. https://example.com) for the Link type.\n\n"
                    f"Got: {d[:50]}{'…' if len(d) > 50 else ''}",
                )
                row.path.setFocus()
                return
            if pt == ProjectType.EXECUTE and not os.path.isfile(d):
                dialogs.error(self, "Invalid file", "Execute / Open file needs an existing file path.")
                row.path.setFocus()
                return
            sub_projects.append(SubProject(
                id=row.sp_id or str(uuid.uuid4()),
                directory=d,
                type=pt,
                name=row.name.text().strip() or None,
                commands=list(row.commands),
            ))

        self.result_project = Project(
            id=self.project.id if self.project else str(uuid.uuid4()),
            name=name,
            icon_path=self._icon.text().strip() or None,
            main_project_folder=self._main_folder.text().strip() or None,
            sub_projects=sub_projects,
            open_count=self.project.open_count if self.project else 0,
        )
        self.accept()

    @classmethod
    def edit(cls, parent: Optional[QWidget], project: Optional[Project] = None) -> Optional[Project]:
        """Show the editor; the saved project, or None if cancelled."""
        dlg = cls(parent, project)
        return dlg.result_project if dlg.exec() == QDialog.DialogCode.Accepted else None
