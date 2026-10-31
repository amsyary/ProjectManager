"""The open drawer: a project's header and one foam slot per folder, each with its tools cut in."""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from models.project import Project, ProjectType, SubProject
from services.editor_launcher import EditorLauncher
from services.project_service import ProjectService
from services.terminal_launcher import TERMINALS, TerminalLauncher
from services.vscode_launch import is_flutter_project, load_launch
from services.vscode_tasks import load_tasks
from ui import dialogs
from ui.flutter_run_window import FlutterRunWindow
from ui.icon_loader import load_icon, load_type_icon
from ui.launch_menu import has_launch_options, quick_start, show_launch_menu
from ui.run_manager import RunManager
from ui.tasks_menu import show_tasks_menu
from ui.theme import RADIUS_PANEL, SIZE_MAIN, SIZE_META, label_font, mono_font, t
from ui.widgets import DymoLabel, FlowLayout, FoamPanel, IconWell, Menu, ToolSlot, paint_foam

EDITORS = {"cursor": "Cursor", "code": "VS Code", "antigravity": "Antigravity", "claude": "Claude"}

_OPEN_ICON = {
    ProjectType.LINK: ("globe", "Open in the browser"),
    ProjectType.DATA_TXT: ("file", "Open in Notepad"),
    ProjectType.EXECUTE: ("external", "Open with its default app"),
}


class ElidedLabel(QLabel):
    """A single-line label that elides to fit, keeping the full text as tooltip."""

    def __init__(self, text: str, mono: bool = False, parent: Optional[QWidget] = None,
                 font=None, mode: Qt.TextElideMode = Qt.TextElideMode.ElideMiddle):
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self.setFont(font or (mono_font(SIZE_META) if mono else label_font(SIZE_META)))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setToolTip(text)
        self._refit()

    def resizeEvent(self, event) -> None:
        self._refit()
        super().resizeEvent(event)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (event.Type.FontChange, event.Type.StyleChange):
            self._refit()

    def _refit(self) -> None:
        fm = QFontMetrics(self.font())
        super().setText(fm.elidedText(self._full, self._mode, max(40, self.width())))


class _ToolFlow(QWidget):
    """Tools aligned right that wrap onto more lines only when the row is too narrow."""

    def __init__(self):
        super().__init__()
        self.flow = FlowLayout(self, spacing=4, align_right=True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def sizeHint(self) -> QSize:
        return self.flow.sizeHint()

    def minimumSizeHint(self) -> QSize:
        return QSize(self.flow.minimumSize().width(), self.minimumHeight())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        height = self.flow.heightForWidth(self.width())
        if height != self.minimumHeight():
            self.setMinimumHeight(height)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.setMinimumHeight(self.flow.heightForWidth(max(self.width(), 1)))


def _tools_box() -> tuple[QWidget, FlowLayout]:
    box = _ToolFlow()
    return box, box.flow


class _Slab(FoamPanel):
    """Icon well, info and tools side by side; tools drop below the info when the slab is narrow."""

    def __init__(self, margins: tuple[int, int, int, int], spacing: int, radius: int = RADIUS_PANEL):
        super().__init__(radius=radius)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(*margins)
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(10)
        self._parts: Optional[tuple] = None
        self._stacked: Optional[bool] = None

    def set_parts(self, well: QWidget, info: QWidget, tools: "_ToolFlow", align: Qt.AlignmentFlag) -> None:
        self._parts = (well, info, tools, align)
        self._grid.addWidget(well, 0, 0, 2, 1, align)
        self._grid.setColumnStretch(1, 1)
        self._arrange()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._arrange()

    def _arrange(self) -> None:
        if not self._parts:
            return
        well, info, tools, align = self._parts
        m = self._grid.contentsMargins()
        gap = self._grid.horizontalSpacing()
        needed = m.left() + m.right() + well.width() + info.minimumWidth() + tools.sizeHint().width() + 2 * gap
        stacked = self.width() < needed
        if stacked == self._stacked:
            return
        self._stacked = stacked
        self._grid.removeWidget(info)
        self._grid.removeWidget(tools)
        tools.flow.set_align_right(not stacked)
        if stacked:
            self._grid.addWidget(info, 0, 1, 1, 2, align)
            self._grid.addWidget(tools, 1, 1, 1, 2)
        else:
            self._grid.addWidget(info, 0, 1, 2, 1, align)
            self._grid.addWidget(tools, 0, 2, 2, 1, align)


class _FolderSlot(_Slab):
    """One folder: double-click opens it like the Open tool."""

    def __init__(self, on_open: Callable[[], None]):
        super().__init__((14, 12, 12, 16), 14, radius=11)
        self._on_open = on_open

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_open()


class _EmptyDrawer(QWidget):
    """An empty foam insert with the outlines of tools that aren't there yet."""

    def __init__(self, title: str, detail: str, action: Optional[ToolSlot] = None):
        super().__init__()
        self.setMinimumHeight(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 170, 40, 40)
        layout.setSpacing(8)
        head = QLabel(title)
        head.setFont(label_font(SIZE_MAIN, semibold=True))
        head.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(head)
        sub = QLabel(detail)
        sub.setProperty("role", "dim")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)
        if action:
            layout.addSpacing(8)
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel = QRectF(self.rect()).adjusted(1, 1, -1, -5)
        paint_foam(p, panel, RADIUS_PANEL, t("foam"))
        # Silhouettes of missing tools, outlined like a shadow board waiting to be filled
        pen = QPen(t("ink_faint", 150), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        cx = panel.center().x()
        shapes = [QRectF(cx - 150, 56, 84, 84), QRectF(cx - 46, 70, 150, 26), QRectF(cx - 46, 108, 96, 26), QRectF(cx + 116, 56, 34, 84)]
        for r in shapes:
            p.drawRoundedRect(r, 8, 8)


class SubProjectPanel(QScrollArea):
    """Shows the selected project's drawer."""

    def __init__(
        self,
        on_sub_project_opened: Callable[[Project], None],
        on_edit_project: Callable[[Project], None],
        on_delete_project: Callable[[Project], None],
        on_add_project: Callable[[], None],
        on_show_log: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._editor = EditorLauncher(ProjectService.get_editor())
        self._terminal = TerminalLauncher(ProjectService.get_terminal())
        self._project: Optional[Project] = None
        self._on_opened = on_sub_project_opened
        self._on_edit = on_edit_project
        self._on_delete = on_delete_project
        self._on_add = on_add_project
        self._on_show_log = on_show_log
        self._start_slots: list[tuple[str, ToolSlot, ToolSlot]] = []  # folder, Start, Log
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._timer = QTimer(self, interval=500)
        self._timer.timeout.connect(self._refresh_run_slots)
        self._timer.start()
        RunManager.get().changed.connect(self._refresh_run_slots)
        self._fade = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=240)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.valueChanged.connect(self._fade_step)
        self._fade.finished.connect(self._fade_done)
        self._content: Optional[QWidget] = None
        self.show_empty("none")

    # -- public --

    @property
    def project(self) -> Optional[Project]:
        return self._project

    def refresh_editor(self) -> None:
        self._editor = EditorLauncher(ProjectService.get_editor())
        if self._project:
            self.set_project(self._project, animate=False)

    def refresh_terminal(self) -> None:
        self._terminal = TerminalLauncher(ProjectService.get_terminal())
        if self._project:
            self.set_project(self._project, animate=False)  # Tooltips name the terminal

    def focus_first_tool(self) -> None:
        """Keyboard path: search, Enter, Enter launches the drawer's first tool (Open all)."""
        if self._content is None:
            return
        slots = self._content.findChildren(ToolSlot)
        if slots:
            slots[0].setFocus(Qt.FocusReason.TabFocusReason)

    def show_empty(self, kind: str, query: str = "", on_clear: Optional[Callable[[], None]] = None) -> None:
        """kind: "none" (nothing picked), "no_projects", or "no_match"."""
        self._project = None
        self._start_slots = []
        if kind == "no_projects":
            add = ToolSlot("Add project", "plus", variant="primary")
            add.clicked.connect(self._on_add)
            empty = _EmptyDrawer("No projects yet", "A project bundles its folders: app, dashboard, functions, docs, files and links.", add)
        elif kind == "no_match":
            clear = ToolSlot("Clear search", "close")
            if on_clear:
                clear.clicked.connect(on_clear)
            empty = _EmptyDrawer(f"Nothing matches “{query}”", "Search looks at project names.", clear)
        else:
            empty = _EmptyDrawer("Pick a drawer", "Choose a project on the left, or press Ctrl+N to add one.")
        self._mount(self._wrap(empty), animate=False)

    def set_project(self, project: Optional[Project], animate: bool = True) -> None:
        if project is None:
            self.show_empty("none")
            return
        self._project = project
        self._mount(self._build(project), animate=animate)

    # -- building --

    def _wrap(self, child: QWidget) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.addWidget(child)
        layout.addStretch()
        return content

    def _mount(self, content: QWidget, animate: bool) -> None:
        self._fade.stop()
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self._content = content
        self.setWidget(content)
        if animate:
            effect = QGraphicsOpacityEffect(content)
            effect.setOpacity(0.0)
            content.setGraphicsEffect(effect)
            self._fade.start()

    def _fade_step(self, value) -> None:
        if self._content is None:
            return
        effect = self._content.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(float(value))
        margin = int(14 * (1.0 - float(value)))
        layout = self._content.layout()
        if layout:
            layout.setContentsMargins(18 + margin, 16, 18 - margin, 18)

    def _fade_done(self) -> None:
        if self._content is not None:
            self._content.setGraphicsEffect(None)  # Crisp text once the drawer is open

    def _build(self, project: Project) -> QWidget:
        self._start_slots = []
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(6)
        root.addWidget(self._header(project))
        root.addSpacing(6)
        if project.sub_projects:
            for sp in project.sub_projects:
                root.addWidget(self._folder_row(sp, project))
        else:
            edit = ToolSlot("Add folders", "edit")
            edit.clicked.connect(lambda: self._on_edit(project))
            root.addWidget(_EmptyDrawer("This drawer is empty", "Edit the project to add its folders, files and links.", edit))
        root.addStretch()
        self._refresh_run_slots()
        return content

    def _header(self, project: Project) -> QWidget:
        panel = _Slab((18, 16, 16, 20), 16)
        well = IconWell(64)
        well.set_pixmap(load_icon(project.icon_path, 48))

        info = QVBoxLayout()
        info.setSpacing(7)
        info.addWidget(DymoLabel(project.name, SIZE_MAIN), 0, Qt.AlignmentFlag.AlignLeft)
        folder = project.main_project_folder
        if folder:
            path = ElidedLabel(folder, mono=True)
            path.setProperty("role", "error" if not os.path.isdir(folder) else "mono")
            if not os.path.isdir(folder):
                path.setToolTip(f"Folder not found: {folder}")
            info.addWidget(path)
        n = len(project.sub_projects)
        meta = QLabel(f"{n} folder{'s' if n != 1 else ''}" + (f"  ·  opened {project.open_count}×" if project.open_count else "")
                      + ("" if folder else "  ·  no main folder"))
        meta.setProperty("role", "dim")
        info.addWidget(meta)
        info_box = QWidget()
        info_box.setLayout(info)
        info.setContentsMargins(0, 0, 0, 0)
        info_box.setMinimumWidth(280)

        box, tools = _tools_box()
        if project.sub_projects:
            open_all = ToolSlot("Open all", "code", variant="primary", tooltip="Open every folder (Ctrl+Enter)")
            open_all.clicked.connect(lambda: self.open_all(project))
            tools.addWidget(open_all)
        explorer = ToolSlot("Explorer", "folder", tooltip="Open the main folder in Explorer")
        explorer.clicked.connect(lambda: self._open_project_folder(project))
        tools.addWidget(explorer)
        if folder:
            term = ToolSlot("Terminal", "terminal", tooltip=f"Open the main folder in {TERMINALS[self._terminal.terminal]}")
            term.clicked.connect(lambda: self._open_terminal(folder))
            tools.addWidget(term)
            self._add_tasks_tool(tools, folder)
            self._add_launch_tools(tools, folder, project.name, project.icon_path)
        edit = ToolSlot("", "edit", variant="quiet", tooltip="Edit project (Ctrl+E)")
        edit.clicked.connect(lambda: self._on_edit(project))
        tools.addWidget(edit)
        more = ToolSlot("", "more", variant="quiet", tooltip="More")
        more.clicked.connect(lambda: self._more_menu(more, project))
        tools.addWidget(more)
        panel.set_parts(well, info_box, box, Qt.AlignmentFlag.AlignTop)
        return panel

    def _folder_row(self, sp: SubProject, project: Project) -> QWidget:
        panel = _FolderSlot(lambda: self._open_one(sp, project))
        well = IconWell(44, fallback="folder")
        well.set_pixmap(load_type_icon(sp.type.value, 28))

        info_box = QWidget()
        info_box.setMinimumWidth(280)
        info = QVBoxLayout(info_box)
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(3)
        name = ElidedLabel(
            sp.display_name() if sp.type != ProjectType.LINK or sp.name else _short_url(sp.directory),
            font=label_font(SIZE_MAIN, semibold=True), mode=Qt.TextElideMode.ElideRight,
        )
        info.addWidget(name)
        meta = QHBoxLayout()
        meta.setSpacing(8)
        kind = QLabel(ProjectType.display_name(sp.type).upper())
        kind.setProperty("role", "caps")
        meta.addWidget(kind)
        path = ElidedLabel(sp.directory, mono=True)
        missing = sp.type != ProjectType.LINK and not os.path.exists(sp.directory)
        path.setProperty("role", "error" if missing else "mono")
        if missing:
            path.setToolTip(f"Not found: {sp.directory}")
        meta.addWidget(path, 1)
        info.addLayout(meta)

        box, tools = _tools_box()
        icon_name, tip = _OPEN_ICON.get(sp.type, ("code", f"Open in {EDITORS.get(self._editor.editor, 'the editor')}"))
        open_btn = ToolSlot("Open", icon_name, tooltip=tip + "  (double-click the row)")
        open_btn.clicked.connect(lambda: self._open_one(sp, project))
        if sp.type != ProjectType.LINK:
            term = ToolSlot("Terminal", "terminal", tooltip=f"Open in {TERMINALS[self._terminal.terminal]}")
            term.clicked.connect(lambda: self._open_terminal(sp.directory))
            if len(sp.commands) == 1:
                cmd = sp.commands[0]
                run = ToolSlot(cmd.display_name() if cmd.name else "Run", "run", tooltip=f"Run in terminal: {cmd.command}")
                run.clicked.connect(lambda: self._open_terminal(sp.directory, cmd.command))
                tools.addWidget(run)
            elif sp.commands:
                run = ToolSlot("Run", "run", arrow=True, tooltip=f"{len(sp.commands)} saved commands")
                run.clicked.connect(lambda: self._run_menu(run, sp))
                tools.addWidget(run)
            self._add_tasks_tool(tools, sp.directory)
            self._add_launch_tools(tools, sp.directory, f"{project.name} · {sp.display_name()}", project.icon_path)
            tools.addWidget(term)
        tools.addWidget(open_btn)
        panel.set_parts(well, info_box, box, Qt.AlignmentFlag.AlignVCenter)
        return panel

    def _add_tasks_tool(self, tools: FlowLayout, folder: str) -> None:
        """A "Tasks" drop-down if folder has a .vscode/tasks.json (read fresh each time)."""
        tasks_file = load_tasks(folder)
        if tasks_file is None:
            return
        btn = ToolSlot("Tasks", "tasks", arrow=True, tooltip="VS Code tasks (.vscode/tasks.json)")
        btn.clicked.connect(lambda: show_tasks_menu(btn, load_tasks(folder) or tasks_file, self._terminal))
        tools.addWidget(btn)

    def _add_launch_tools(self, tools: FlowLayout, folder: str, name: str, icon_path: Optional[str]) -> None:
        """"Launch" for launch.json configurations and Flutter run; "Start" for Flutter quick start."""
        if not has_launch_options(folder, load_launch(folder)):
            return
        btn = ToolSlot("Launch", "launch", arrow=True, tooltip="Launch configurations (.vscode/launch.json) and Flutter run")
        btn.clicked.connect(lambda: show_launch_menu(btn, folder, load_launch(folder), self._terminal, name, icon_path))
        tools.addWidget(btn)
        if is_flutter_project(folder):
            start = ToolSlot("Start", "play")
            start.reserve("Building 0:00", "Stopping 0:00", "Running · 2", out=True)  # Rows don't reflow when a build starts
            start.clicked.connect(lambda: self._start_or_focus(start, folder, name, icon_path))
            tools.addWidget(start)
            log = ToolSlot("Log", "logs", tooltip="Show this folder's run log in the sidebar")
            log.set_ghost_when_disabled(True)  # An empty cut-out until something has run
            log.clicked.connect(lambda: self._on_show_log(folder))
            tools.addWidget(log)
            self._start_slots.append((folder, start, log))

    # -- running state: a tool that is out of its slot shows the yellow floor --

    def _refresh_run_slots(self) -> None:
        manager = RunManager.get()
        alive = []
        for folder, slot, log in self._start_slots:
            try:
                state, seconds, running = manager.folder_state(folder)
                if state is None:
                    slot.set_out(False)
                    slot.setText("Start")
                    slot.set_icon_name("play")
                    slot.setToolTip("Run in the background on the saved devices (the log is in the sidebar)")
                else:
                    slot.set_out(True)
                    slot.set_icon_name("pulse" if state == "running" else "restart")
                    label = {"running": "Running", "building": "Building", "stopping": "Stopping"}[state]
                    if state == "running":
                        label += f" · {running}" if running > 1 else ""
                    else:
                        label += f" {seconds // 60}:{seconds % 60:02d}"
                    slot.setText(label)
                    slot.setToolTip("Show the Flutter window")
                log.setEnabled(bool(manager.runs(folder)))
                alive.append((folder, slot, log))
            except RuntimeError:
                pass  # Slot was deleted with an old drawer
        self._start_slots = alive

    def _start_or_focus(self, button: ToolSlot, folder: str, name: str, icon_path: Optional[str]) -> None:
        """Start runs in the background; while it runs, the slot opens the Flutter window."""
        if RunManager.get().folder_state(folder)[0] is not None:
            FlutterRunWindow.open(None, folder, load_launch(folder), name=name, icon_path=icon_path)
            return
        quick_start(button, folder, name, icon_path)
        self._refresh_run_slots()

    # -- actions --

    def open_all(self, project: Project) -> None:
        for sp in project.sub_projects:
            self._open_sub_project(sp)
            self._on_opened(project)

    def _open_one(self, sp: SubProject, project: Project) -> None:
        if self._open_sub_project(sp):
            self._on_opened(project)

    def _open_sub_project(self, sp: SubProject) -> bool:
        """Open in the editor/app, and start any commands marked Run when opened."""
        if not self._editor.open(sp.directory, sp.type):
            what = {
                ProjectType.LINK: "the browser",
                ProjectType.DATA_TXT: "Notepad",
                ProjectType.EXECUTE: "its default app",
            }.get(sp.type, EDITORS.get(self._editor.editor, "the editor"))
            dialogs.error(self.window(), "Open", f"Could not open {sp.display_name()} in {what}:\n{sp.directory}\n\n"
                          "Check that it exists and the app is installed.")
            return False
        if sp.type != ProjectType.LINK:
            for c in sp.commands:
                if c.run_on_open:
                    self._open_terminal(sp.directory, c.command)
        return True

    def _open_project_folder(self, project: Project) -> None:
        if not project.main_project_folder:
            dialogs.info(self.window(), "Project folder", "This project has no main folder. Edit the project to add one.")
        elif not self._editor.open_in_explorer(project.main_project_folder):
            dialogs.error(self.window(), "Project folder", f"Folder not found:\n{project.main_project_folder}")

    def _open_terminal(self, path: str, command: Optional[str] = None) -> None:
        """Open path in the chosen terminal (running command if given); show an error on failure."""
        if not self._terminal.open(path, command):
            dialogs.error(
                self.window(), "Terminal",
                f"Could not open {TERMINALS[self._terminal.terminal]} in:\n{path}\n\n"
                "Check that the folder exists and the terminal is installed.",
            )

    def _run_menu(self, button: ToolSlot, sp: SubProject) -> None:
        menu = Menu(button)
        for c in sp.commands:
            label = c.display_name()
            if c.name and c.name.strip():
                label = f"{label}   ({c.command})"
            menu.add(label, lambda _=False, c=c: self._open_terminal(sp.directory, c.command), icon_name="run")
        menu.addSeparator()
        menu.add("Run all", lambda: [self._open_terminal(sp.directory, c.command) for c in sp.commands])
        menu.popup_below(button)

    def _more_menu(self, button: ToolSlot, project: Project) -> None:
        menu = Menu(button)
        menu.add("Edit project", lambda: self._on_edit(project), icon_name="edit")
        menu.addSeparator()
        menu.add("Delete project", lambda: self._on_delete(project), icon_name="trash")
        menu.popup_below(button)


def _short_url(url: str) -> str:
    return url.split("://", 1)[-1].rstrip("/")
