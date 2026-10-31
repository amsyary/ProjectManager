"""Main window: the cabinet. Drawer fronts on the left, the open drawer beside them."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QSizePolicy, QSplitter,
    QVBoxLayout, QWidget,
)

from models.project import Project
from services.project_service import ProjectService
from services.terminal_launcher import TERMINALS
from services.vscode_launch import load_launch
from ui import dialogs, icons
from ui.add_edit_dialog import ProjectDialog
from ui.flutter_run_window import FlutterRunWindow
from ui.icon_loader import clear_cache
from ui.log_panel import LogPanel
from ui.project_card import ProjectRail
from ui.run_manager import RunManager
from ui.scrcpy_button import ScrcpyButton
from ui.sub_project_panel import EDITORS, SubProjectPanel
from ui.text_panel import TextPanel
from ui.theme import Theme, apply_title_bar, label_font, t
from ui.widgets import Combo, Menu, SearchField, ToolSlot, paint_cut


def app_icon() -> QIcon:
    """The app mark: a yellow drawer cut into charcoal foam."""
    ico = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#26292D"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
        inset = size * 0.16
        p.drawPixmap(int(inset), int(inset), icons.pixmap("drawer", "#F2B705", int(size - 2 * inset), dpr=1.0))
        p.end()
        ico.addPixmap(pm)
    return ico


def _caps(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("role", "caps")
    return label


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Manager")
        self.setWindowIcon(app_icon())
        self.resize(1200, 760)
        self.setMinimumSize(880, 540)

        self._service = ProjectService()
        self._selected_id: Optional[str] = None
        self._build()
        self._shortcuts()
        self._refresh_rail()

        self._run_timer = QTimer(self, interval=1000)
        self._run_timer.timeout.connect(self._rail.refresh_running)
        self._run_timer.start()
        RunManager.get().changed.connect(self._on_runs_changed)
        self._on_runs_changed()
        QApplication.instance().aboutToQuit.connect(self._shutdown_runs)

    # -- layout --

    def _build(self) -> None:
        cabinet = QWidget()
        cabinet.setObjectName("Cabinet")
        root = QVBoxLayout(cabinet)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._top_bar())

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setChildrenCollapsible(False)

        rail = QWidget()
        rail.setObjectName("Rail")
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rail.setMinimumWidth(250)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 12, 0, 12)
        rail_layout.setSpacing(8)
        self._search = SearchField("Search projects   Ctrl+F")
        self._search.textChanged.connect(lambda _: self._refresh_rail())
        self._search.navigate.connect(lambda d: self._rail.step(d))
        self._search.accepted.connect(self._search_accepted)
        search_row = QHBoxLayout()
        search_row.setContentsMargins(12, 0, 12, 0)
        search_row.addWidget(self._search)
        rail_layout.addLayout(search_row)

        self._rail = ProjectRail()
        self._rail.set_running_check(self._project_running)
        self._rail.project_selected.connect(self._on_project_selected)
        self._rail.edit_requested.connect(self._on_edit_project)
        self._rail.delete_requested.connect(self._on_delete_project)
        self._rail.open_all_requested.connect(lambda p: self._drawer.open_all(p))
        self._rail.typed.connect(self._type_ahead)
        self._rail.entered.connect(self._drawer_focus)
        rail_layout.addWidget(self._rail, 1)

        add = ToolSlot("Add project", "plus", tooltip="Add a project (Ctrl+N)")
        add.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add.clicked.connect(self._on_add_project)
        add_row = QHBoxLayout()
        add_row.setContentsMargins(12, 0, 12, 0)
        add_row.addWidget(add)
        rail_layout.addLayout(add_row)

        self._drawer = SubProjectPanel(
            on_sub_project_opened=self._on_sub_project_opened,
            on_edit_project=self._on_edit_project,
            on_delete_project=self._on_delete_project,
            on_add_project=self._on_add_project,
            on_show_log=lambda folder: self.show_logs(folder),
        )
        self._logs = LogPanel()
        self._logs.hide()
        self._logs.close_requested.connect(lambda: self._logs_btn.setChecked(False))
        self._logs.open_window.connect(self._open_run_window)
        self._texts = TextPanel(self._service)
        self._texts.hide()

        self._splitter.addWidget(rail)
        self._splitter.addWidget(self._drawer)
        self._splitter.addWidget(self._logs)
        self._splitter.addWidget(self._texts)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setStretchFactor(3, 0)
        self._splitter.setSizes([300, 900, 0, 0])
        root.addWidget(self._splitter, 1)
        self.setCentralWidget(cabinet)

    def _top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Rail")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 8, 12, 8)
        row.setSpacing(8)

        self._mark = QLabel()
        self._mark.setPixmap(icons.pixmap("drawer", t("yellow"), 20))
        row.addWidget(self._mark)
        self._title = QLabel("Project Manager")
        self._title.setFont(label_font(semibold=True))
        row.addWidget(self._title)
        row.addStretch()

        self._editor_caps = _caps("Editor")
        row.addWidget(self._editor_caps)
        self._editor_box = Combo()
        for key, name in EDITORS.items():
            self._editor_box.addItem(name, key)
        saved = ProjectService.get_editor()
        self._editor_box.setCurrentIndex(max(0, self._editor_box.findData(saved)))
        self._editor_box.setMinimumWidth(130)
        self._editor_box.setToolTip("Editor that Open uses")
        self._editor_box.currentIndexChanged.connect(self._on_editor_change)
        row.addWidget(self._editor_box)
        row.addSpacing(8)

        self._terminal_caps = _caps("Terminal")
        row.addWidget(self._terminal_caps)
        self._terminal_box = Combo()
        for key, name in TERMINALS.items():
            self._terminal_box.addItem(name, key)
        self._terminal_box.setCurrentIndex(max(0, self._terminal_box.findData(ProjectService.get_terminal())))
        self._terminal_box.setMinimumWidth(176)
        self._terminal_box.setToolTip("Terminal that Terminal, Run, tasks and launch use")
        self._terminal_box.currentIndexChanged.connect(self._on_terminal_change)
        row.addWidget(self._terminal_box)
        row.addSpacing(10)

        row.addWidget(ScrcpyButton())
        self._logs_btn = ToolSlot("Logs", "logs", compact=True, tooltip="Show the run logs (Ctrl+L)")
        self._logs_btn.reserve("Logs · 9")
        self._logs_btn.setCheckable(True)
        self._logs_btn.toggled.connect(self._toggle_log_panel)
        row.addWidget(self._logs_btn)
        self._texts_btn = ToolSlot("Snippets", "note", compact=True, tooltip="Show saved text snippets")
        self._texts_btn.setCheckable(True)
        self._texts_btn.toggled.connect(self._toggle_text_panel)
        row.addWidget(self._texts_btn)
        self._theme_btn = ToolSlot("", "sun" if Theme.get().is_dark else "moon", compact=True, variant="quiet")
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._update_theme_btn()
        row.addWidget(self._theme_btn)
        more = ToolSlot("", "more", compact=True, variant="quiet", tooltip="Export or import projects")
        more.clicked.connect(lambda: self._file_menu(more))
        row.addWidget(more)
        return bar

    def _shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_add_project)
        QShortcut(QKeySequence("Ctrl+E"), self, lambda: self._with_current(self._on_edit_project))
        QShortcut(QKeySequence("Ctrl+Return"), self, lambda: self._with_current(self._drawer.open_all))
        QShortcut(QKeySequence("F5"), self, self._reload_drawer)
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self._logs_btn.setChecked(not self._logs_btn.isChecked()))

    def showEvent(self, event) -> None:
        apply_title_bar(self)
        super().showEvent(event)
        QTimer.singleShot(0, self._search.setFocus)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        roomy = self.width() >= 1080  # Labels give way before the controls do
        for w in (self._title, self._editor_caps, self._terminal_caps):
            w.setVisible(roomy)

    # -- rail --

    def _visible_projects(self) -> list[Project]:
        projects = self._service.get_all()
        query = self._search.text().strip().lower()
        if query:
            projects = [p for p in projects if query in p.name.lower()]
        projects.sort(key=lambda p: p.open_count, reverse=True)
        return projects

    def _refresh_rail(self) -> None:
        projects = self._visible_projects()
        query = self._search.text().strip()
        ids = [p.id for p in projects]
        if query and projects and self._selected_id not in ids:
            self._selected_id = projects[0].id  # Typing narrows straight to the best match
        self._rail.set_projects(projects, self._selected_id)

        if not self._service.get_all():
            self._drawer.show_empty("no_projects")
        elif not projects:
            self._drawer.show_empty("no_match", query, on_clear=self._search.clear)
        elif self._selected_id in ids:
            selected = next(p for p in projects if p.id == self._selected_id)
            if self._drawer.project is None or self._drawer.project.id != selected.id:
                self._drawer.set_project(selected)
        elif self._drawer.project is None or self._drawer.project.id not in ids:
            self._drawer.show_empty("none")

    def _on_project_selected(self, project: Optional[Project]) -> None:
        if project is None:
            return
        same = self._drawer.project is not None and self._drawer.project.id == project.id
        self._selected_id = project.id
        if not same:
            self._drawer.set_project(project)

    def _project_running(self, project: Project) -> bool:
        folders = [project.main_project_folder] if project.main_project_folder else []
        folders += [sp.directory for sp in project.sub_projects]
        manager = RunManager.get()
        return any(manager.folder_state(f)[0] for f in folders)

    def _search_accepted(self) -> None:
        if self._rail.count():
            if self._rail.currentRow() < 0:
                self._rail.setCurrentRow(0)
            self._rail.setFocus()

    def _drawer_focus(self) -> None:
        self._drawer.focus_first_tool()

    def _focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def _type_ahead(self, text: str) -> None:
        self._search.setFocus()
        self._search.insert(text)

    def _with_current(self, action) -> None:
        project = self._drawer.project
        if project is not None:
            action(project)

    def _reload_drawer(self) -> None:
        """Re-read tasks.json / launch.json and folder state."""
        if self._drawer.project is not None:
            self._drawer.set_project(self._drawer.project, animate=False)

    # -- projects --

    def _on_sub_project_opened(self, project: Project) -> None:
        self._service.increment_open_count(project.id)
        self._rail.set_projects(self._visible_projects(), self._selected_id)

    def _on_add_project(self) -> None:
        project = ProjectDialog.edit(self, None)
        if project is None:
            return
        self._service.add(project)
        self._selected_id = project.id
        self._search.clear()
        self._refresh_rail()
        self._drawer.set_project(project)

    def _on_edit_project(self, project: Project) -> None:
        updated = ProjectDialog.edit(self, project)
        if updated is None:
            return
        self._service.update(updated)
        clear_cache()
        self._refresh_rail()
        if self._drawer.project is not None and self._drawer.project.id == updated.id:
            self._drawer.set_project(updated, animate=False)

    def _on_delete_project(self, project: Project) -> None:
        if not dialogs.confirm(
            self, "Delete project", f"Delete “{project.name}”? This cannot be undone.\n\nOnly the entry is removed; no files are touched.",
            "Delete project", danger=True,
        ):
            return
        self._service.delete(project.id)
        if self._selected_id == project.id:
            self._selected_id = None
            self._drawer.show_empty("none")
        self._refresh_rail()

    # -- top bar --

    def _on_editor_change(self) -> None:
        ProjectService.set_editor(self._editor_box.currentData())
        self._drawer.refresh_editor()

    def _on_terminal_change(self) -> None:
        ProjectService.set_terminal(self._terminal_box.currentData())
        self._drawer.refresh_terminal()

    def _toggle_text_panel(self, show: bool) -> None:
        self._texts.setVisible(show)
        if show:
            self._texts.refresh()
            self._make_room(3, 320)

    def _make_room(self, index: int, width: int) -> None:
        """Give the side panel at splitter index width, taken from the drawer."""
        sizes = self._splitter.sizes()
        need = sum(sizes) - sizes[1] - sizes[index] + width + 400
        if self.width() < need + 40 and not self.isMaximized():
            self.resize(min(need + 40, self.screen().availableGeometry().width()), self.height())
            sizes = self._splitter.sizes()
        sizes[1] = max(400, sizes[1] - width + sizes[index])
        sizes[index] = width
        self._splitter.setSizes(sizes)

    # -- run logs --

    def show_logs(self, folder: Optional[str] = None) -> None:
        """Open the log sidebar, on one of folder's runs if given."""
        if folder:
            self._logs.show_folder(folder)
        self._logs_btn.setChecked(True)

    def _toggle_log_panel(self, show: bool) -> None:
        if show == self._logs.isVisible():
            return
        self._logs.setVisible(show)
        if show:
            self._make_room(2, 440)
        self._on_runs_changed()

    def _on_runs_changed(self) -> None:
        manager = RunManager.get()
        active = len(manager.active_runs())
        self._logs_btn.setText(f"Logs · {active}" if active else "Logs")
        self._logs_btn.setVisible(bool(manager.runs()) or self._logs.isVisible())
        self._rail.refresh_running()

    def _open_run_window(self, rid: str) -> None:
        run = RunManager.get().run(rid)
        if run:
            FlutterRunWindow.open(None, run.folder, load_launch(run.folder), name=run.name, icon_path=run.icon_path)

    def _shutdown_runs(self) -> None:
        FlutterRunWindow.save_all()
        RunManager.get().shutdown_all()

    def _update_theme_btn(self) -> None:
        dark = Theme.get().is_dark
        self._theme_btn.set_icon_name("sun" if dark else "moon")
        self._theme_btn.setToolTip("Switch to light mode" if dark else "Switch to night mode")

    def _toggle_theme(self) -> None:
        theme = Theme.get()
        theme.set_dark(not theme.is_dark)
        ProjectService.set_theme("dark" if theme.is_dark else "light")
        self._update_theme_btn()
        self._mark.setPixmap(icons.pixmap("drawer", t("yellow"), 20))

    def _file_menu(self, button: ToolSlot) -> None:
        menu = Menu(button)
        menu.add("Export projects…", self._on_export, icon_name="export")
        menu.add("Import projects…", self._on_import, icon_name="import")
        menu.popup_below(button)

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export projects", "projects.json", "JSON files (*.json);;All files (*.*)")
        if not path:
            return
        if self._service.export_to_file(path):
            dialogs.info(self, "Export", "Projects exported.")
        else:
            dialogs.error(self, "Export", "Could not write the export file.")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import projects", "", "JSON files (*.json);;All files (*.*)")
        if not path:
            return
        projects = self._service.import_from_file(path)
        if projects is None:
            dialogs.error(self, "Import", "Could not read that file. It is not a valid projects export.")
            return

        current_count = len(self._service.get_all())
        if current_count:
            choice = dialogs.choose(
                self, "Import",
                f"The file has {len(projects)} project(s). You have {current_count}.\n\n"
                "Merge adds new projects and updates ones with the same id.\n"
                "Overwrite replaces all of your current projects.",
                ["Merge", "Overwrite"],
            )
            if choice is None:
                return
            if choice == 1:
                if not dialogs.confirm(
                    self, "Overwrite projects",
                    f"Replace all {current_count} current project(s) with {len(projects)} imported project(s)?",
                    "Overwrite", danger=True,
                ):
                    return
                self._service.replace_all(projects)
            else:
                self._service.merge_projects(projects)
        else:
            self._service.replace_all(projects)

        self._selected_id = None
        self._drawer.show_empty("none")
        self._refresh_rail()
        dialogs.info(self, "Import", f"Imported {len(projects)} project(s).")

    # -- closing --

    def closeEvent(self, event) -> None:
        self._shutdown_runs()  # Don't leave `flutter run` processes behind
        event.accept()
        QApplication.instance().quit()
