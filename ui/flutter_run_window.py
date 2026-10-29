"""Window that runs a Flutter app like VS Code: pick device and mode, hot reload/restart, toggles."""

from __future__ import annotations

import queue
import shlex
import threading
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QSizePolicy, QVBoxLayout, QWidget,
)

from services.project_service import ProjectService
from services.flutter_runner import (
    TOGGLES, STOP_GRACE_SECONDS, FlutterDevice, FlutterError, FlutterSession,
    detect_flavors, find_flutter, list_devices,
)
from services.vscode_launch import (
    FLUTTER_MODES, FlutterRunSettings, LaunchConfig, LaunchError, LaunchFile, flutter_settings,
)
from ui import dialogs
from ui.icon_loader import load_icon
from ui.theme import SIZE_META, Theme, apply_title_bar, mono_font, t
from ui.widgets import Combo, DymoLabel, FoamPanel, IconWell, ScanBar, StatusLamp, ToolSlot

POLL_MS = 100
MAX_LOG_LINES = 5000
CUSTOM = "Custom"


def _caps(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("role", "caps")
    return label


class FlutterRunWindow(QWidget):
    """One window per folder; opening it again just brings it to the front."""

    _windows: dict[str, "FlutterRunWindow"] = {}

    @classmethod
    def open(
        cls, parent: QWidget, folder: str, launch: Optional[LaunchFile],
        config_name: Optional[str] = None, autorun: bool = False,
        name: str = "", icon_path: Optional[str] = None,
    ) -> None:
        """Open the window. autorun: start the app right away with the saved device and settings.

        name / icon_path identify the project in the window's header and taskbar icon.
        """
        window = cls._windows.get(folder)
        if window is not None:
            window.showNormal()
            window.raise_()
            window.activateWindow()
            window.select_config(config_name)
            if autorun:
                window.quick_start()
            return
        window = cls(folder, launch, config_name, autorun, name, icon_path)
        cls._windows[folder] = window
        window.show()

    @classmethod
    def shutdown_all(cls) -> None:
        """Stop every running app (called when the whole program closes)."""
        for window in list(cls._windows.values()):
            window._stop_and_wait()
            window._save()

    @classmethod
    def session_state(cls, folder: str) -> tuple[Optional[str], int]:
        """("building" | "running" | "stopping" | None, seconds busy) for the folder's window."""
        window = cls._windows.get(folder)
        session = window._session if window else None
        if not session or not session.running:
            return None, 0
        seconds = int(time.monotonic() - window._busy_since)
        if window._stopping:
            return "stopping", seconds
        if session.started:
            return "running", 0
        return "building", seconds

    @classmethod
    def focus(cls, folder: str) -> bool:
        window = cls._windows.get(folder)
        if window is None:
            return False
        window.showNormal()
        window.raise_()
        window.activateWindow()
        return True

    def __init__(
        self, folder: str, launch: Optional[LaunchFile], config_name: Optional[str],
        autorun: bool = False, name: str = "", icon_path: Optional[str] = None,
    ):
        super().__init__(None, Qt.WindowType.Window)
        self.setObjectName("FlutterRunWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._project_name = name
        self._icon_path = icon_path
        self._folder = folder
        self._flutter = find_flutter()
        self._flavors = detect_flavors(folder)
        self._session: Optional[FlutterSession] = None
        self._devices: list[FlutterDevice] = []
        self._device_results: queue.Queue = queue.Queue()
        self._configs: dict[str, LaunchConfig] = {
            c.name: c for c in (launch.configs if launch else []) if c.kind == "flutter"
        }
        self._wanted_device: Optional[str] = None  # deviceId to select once devices are listed
        self._toggle_buttons: dict[str, ToolSlot] = {}
        self._cwd = folder  # Where flutter runs; a launch.json "cwd" can point at a sub-folder
        self._env: dict = {}
        self._app_args: list[str] = []
        self._status_text = "Stopped"
        self._busy_since = time.monotonic()  # When the current build/stop began
        self._stopping = False
        self._autorun = autorun  # Run as soon as the device list is in
        self._loading = True  # Don't save while restoring

        self.setWindowTitle(f"{name} - Flutter" if name else f"Flutter - {folder}")
        self.resize(900, 760)
        self.setMinimumSize(700, 560)
        big = load_icon(icon_path, 64)
        if big:
            self.setWindowIcon(QIcon(big))  # Taskbar / title bar, to tell the windows apart
        self._build()
        QShortcut(QKeySequence("Ctrl+R"), self, self._hot_reload)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self._hot_restart)

        self._save_timer = QTimer(self, singleShot=True, interval=400)
        self._save_timer.timeout.connect(self._save)
        self._timer = QTimer(self, interval=POLL_MS)
        self._timer.timeout.connect(self._tick)

        self._restore(config_name)
        self._loading = False
        self._refresh_devices()
        self._update_controls()
        self._timer.start()
        Theme.get().changed.connect(self._retheme)

        if not self._flutter:
            self._log("Flutter was not found. Add flutter\\bin to PATH (or set FLUTTER_ROOT).", "error")

    # -- layout --

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(14)
        well = IconWell(52, fallback="launch")
        well.set_pixmap(load_icon(self._icon_path, 40))
        header.addWidget(well)
        titles = QVBoxLayout()
        titles.setSpacing(6)
        titles.addWidget(DymoLabel(self._project_name or "Flutter run"), 0, Qt.AlignmentFlag.AlignLeft)
        path = QLabel(self._folder)
        path.setProperty("role", "mono")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        titles.addWidget(path)
        header.addLayout(titles, 1)
        root.addLayout(header)

        # Run settings
        form_panel = FoamPanel()
        form = QGridLayout(form_panel)
        form.setContentsMargins(18, 16, 18, 20)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)

        self._config_box = Combo()
        self._config_box.addItems([CUSTOM, *self._configs])
        self._config_box.activated.connect(lambda _: self._on_config_picked())
        form.addWidget(_caps("Configuration"), 0, 0)
        form.addWidget(self._config_box, 0, 1, 1, 2)

        self._device_box = Combo()
        self._device_box.activated.connect(lambda _: self._device_picked())
        self._refresh_btn = ToolSlot("", "restart", tooltip="Look for devices again")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        form.addWidget(_caps("Device"), 1, 0)
        form.addWidget(self._device_box, 1, 1)
        form.addWidget(self._refresh_btn, 1, 2)

        modes = QHBoxLayout()
        modes.setSpacing(4)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: dict[str, ToolSlot] = {}
        for mode in FLUTTER_MODES:
            btn = ToolSlot(mode.capitalize(), compact=True)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, m=mode: self._on_mode_picked(m))
            self._mode_group.addButton(btn)
            self._mode_buttons[mode] = btn
            modes.addWidget(btn)
        modes.addStretch()
        form.addWidget(_caps("Mode"), 2, 0)
        form.addLayout(modes, 2, 1, 1, 2)

        self._target_edit = QLineEdit("lib/main.dart")
        self._target_edit.setProperty("mono", True)
        if self._flavors:
            self._flavor_edit = Combo()
            self._flavor_edit.setEditable(True)
            self._flavor_edit.addItems(["", *self._flavors])
            self._flavor_line = self._flavor_edit.lineEdit()
        else:
            self._flavor_edit = QLineEdit()
            self._flavor_line = self._flavor_edit
        self._flavor_line.setPlaceholderText("none")
        self._args_edit = QLineEdit()
        self._args_edit.setProperty("mono", True)
        self._args_edit.setPlaceholderText("--dart-define=KEY=value")
        for row, (label, field) in enumerate(
            (("Target", self._target_edit), ("Flavor", self._flavor_edit), ("Extra args", self._args_edit)),
            start=3,
        ):
            form.addWidget(_caps(label), row, 0)
            form.addWidget(field, row, 1, 1, 2)
        if self._flavors:
            hint = QLabel("This project has flavors: " + ", ".join(self._flavors))
            hint.setProperty("role", "dim")
            form.addWidget(hint, 6, 1, 1, 2)
        for line in (self._target_edit, self._flavor_line, self._args_edit):
            line.textChanged.connect(self._schedule_save)
        self._form_widgets: list[QWidget] = [
            self._config_box, self._device_box, self._refresh_btn, *self._mode_buttons.values(),
            self._target_edit, self._flavor_edit, self._args_edit,
        ]
        root.addWidget(form_panel)

        # Controls
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self._run_btn = ToolSlot("Run", "play", variant="primary")
        self._run_btn.clicked.connect(self._run)
        self._stop_btn = ToolSlot("Stop", "stop", variant="danger")
        self._stop_btn.clicked.connect(self._stop)
        self._reload_btn = ToolSlot("Hot reload", "bolt", tooltip="Hot reload (Ctrl+R)")
        self._reload_btn.clicked.connect(self._hot_reload)
        self._restart_btn = ToolSlot("Hot restart", "restart", tooltip="Hot restart (Ctrl+Shift+R)")
        self._restart_btn.clicked.connect(self._hot_restart)
        for w in (self._run_btn, self._stop_btn):
            bar.addWidget(w)
        bar.addSpacing(10)
        for w in (self._reload_btn, self._restart_btn):
            bar.addWidget(w)
        bar.addSpacing(14)
        self._lamp = StatusLamp()
        bar.addWidget(self._lamp)
        self._status = QLabel("Stopped")
        self._status.setProperty("role", "title")
        bar.addWidget(self._status, 1)
        keys = QLabel("Ctrl+R reload · Ctrl+Shift+R restart")
        keys.setProperty("role", "dim")
        bar.addWidget(keys)
        controls = QVBoxLayout()
        controls.setSpacing(8)
        controls.addLayout(bar)
        self._progress = ScanBar()  # Shown while building/stopping
        controls.addWidget(self._progress)
        root.addLayout(controls)

        # Service extension toggles
        toggles_panel = FoamPanel()
        toggles = QGridLayout(toggles_panel)
        toggles.setContentsMargins(14, 12, 14, 16)
        toggles.setHorizontalSpacing(6)
        toggles.setVerticalSpacing(6)
        for i, tg in enumerate(TOGGLES):
            btn = ToolSlot(tg.label, compact=True)
            btn.setCheckable(True)
            btn.set_ghost_when_disabled(True)  # Empty cut-outs until the app runs
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, tg=tg: self._toggle(tg))
            toggles.addWidget(btn, i // 3, i % 3)
            self._toggle_buttons[tg.method] = btn
        root.addWidget(toggles_panel)

        # Log
        log_head = QHBoxLayout()
        log_head.addWidget(_caps("flutter run log"))
        log_head.addStretch()
        clear = ToolSlot("Clear log", "erase", variant="quiet", compact=True)
        clear.clicked.connect(self._clear_log)
        log_head.addWidget(clear)
        root.addLayout(log_head)
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(MAX_LOG_LINES)
        self._log_text.setFont(mono_font(SIZE_META + 1))
        self._log_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        root.addWidget(self._log_text, 1)

    def showEvent(self, event) -> None:
        apply_title_bar(self)
        super().showEvent(event)

    def _retheme(self) -> None:
        self.update()

    # -- saved settings --

    def _mode(self) -> str:
        return next((m for m, b in self._mode_buttons.items() if b.isChecked()), "debug")

    def _set_mode(self, mode: str) -> None:
        self._mode_buttons.get(mode, self._mode_buttons["debug"]).setChecked(True)

    def _on_mode_picked(self, mode: str) -> None:
        self._set_mode(mode)
        self._update_controls()
        self._schedule_save()

    def _flavor(self) -> str:
        return self._flavor_line.text()

    def _restore(self, config_name: Optional[str]) -> None:
        """Start from the saved settings; a config picked from the menu overrides them."""
        saved = ProjectService.get_flutter_run(self._folder)
        name = config_name or saved.get("config")
        if name in self._configs:
            self._config_box.setCurrentText(name)
            self._apply_config(name)
        else:
            self._apply_config(CUSTOM)
        if not config_name:
            self._target_edit.setText(saved.get("target") or self._target_edit.text())
            self._set_mode(saved.get("mode") if saved.get("mode") in FLUTTER_MODES else self._mode())
            self._flavor_line.setText(saved.get("flavor", self._flavor()))
            self._args_edit.setText(saved.get("args", self._args_edit.text()))
        if saved.get("device") and (not config_name or not self._wanted_device):
            self._wanted_device = saved["device"]
        self._update_controls()

    def _schedule_save(self, *_) -> None:
        if not self._loading:
            self._save_timer.start()

    def _save(self) -> None:
        self._save_timer.stop()
        ProjectService.set_flutter_run(self._folder, {
            "config": self._config_box.currentText(),
            "device": self._wanted_device,
            "mode": self._mode(),
            "target": self._target_edit.text(),
            "flavor": self._flavor(),
            "args": self._args_edit.text(),
        })

    def _device_picked(self) -> None:
        self._wanted_device = self._selected_device_id()
        self._schedule_save()

    def quick_start(self) -> None:
        """Run with the saved settings once the devices are listed (or now if they already are)."""
        if self._busy():
            return
        if self._devices:
            self._autorun_now()
        else:
            self._autorun = True

    def _autorun_now(self) -> None:
        self._autorun = False
        if self._busy() or not self._flutter:
            return
        if not self._wanted_device:
            self._log("Quick start: no device saved yet. Pick a device and press Run once.", "note")
        elif self._selected_device_id() != self._wanted_device:
            self._log(f"Quick start: saved device {self._wanted_device} is not connected. Pick another and press Run.", "note")
        else:
            self._run()

    # -- configuration and devices --

    def select_config(self, name: Optional[str]) -> None:
        if name in self._configs and not (self._session and self._session.running):
            self._config_box.setCurrentText(name)
            self._apply_config(name)

    def _on_config_picked(self) -> None:
        self._apply_config(self._config_box.currentText())
        self._schedule_save()

    def _apply_config(self, name: str) -> None:
        config = self._configs.get(name)
        if config is None:
            settings = FlutterRunSettings(cwd=self._folder)
        else:
            try:
                settings = flutter_settings(self._folder, config)
            except LaunchError as e:
                dialogs.error(self, "launch.json", str(e))
                return
        self._cwd = settings.cwd
        self._env = settings.env
        self._app_args = settings.app_args
        self._target_edit.setText(settings.target)
        self._set_mode(settings.mode)
        self._flavor_line.setText(settings.flavor)
        self._args_edit.setText(shlex.join(settings.tool_args))
        self._wanted_device = settings.device_id or self._selected_device_id() or self._wanted_device
        self._select_wanted_device()
        self._update_controls()

    def _refresh_devices(self) -> None:
        if not self._flutter:
            return
        self._refresh_btn.setEnabled(False)
        self._device_box.clear()
        self._device_box.setPlaceholderText("Looking for devices…")
        flutter = self._flutter

        def work():
            try:
                self._device_results.put((list_devices(flutter), None))
            except FlutterError as e:
                self._device_results.put((None, str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _devices_loaded(self, devices: Optional[list[FlutterDevice]], error: Optional[str]) -> None:
        self._refresh_btn.setEnabled(not self._busy())
        if error:
            self._device_box.setPlaceholderText("")
            self._autorun = False
            self._log(error, "error")
            return
        self._devices = devices
        self._device_box.clear()
        self._device_box.addItems([d.display_name() for d in devices])
        if not devices:
            self._device_box.setPlaceholderText("No devices found")
            self._log("No devices found. Connect a phone with USB debugging, or start an emulator.", "note")
            self._autorun = False
            return
        self._select_wanted_device()
        if self._autorun:
            self._autorun_now()

    def _select_wanted_device(self) -> None:
        if not self._devices:
            return
        index = next((i for i, d in enumerate(self._devices) if d.id == self._wanted_device), None)
        if index is None:
            current = self._device_box.currentIndex()
            index = current if current >= 0 else 0
        self._device_box.setCurrentIndex(index)

    def _selected_device_id(self) -> Optional[str]:
        index = self._device_box.currentIndex()
        return self._devices[index].id if 0 <= index < len(self._devices) else None

    # -- running --

    def _busy(self) -> bool:
        return bool(self._session and self._session.running)

    def _run(self) -> None:
        if not self._flutter:
            dialogs.error(self, "Flutter", "Flutter was not found. Add flutter\\bin to PATH.")
            return
        device = self._selected_device_id()
        self._wanted_device = device or self._wanted_device
        if not device:
            dialogs.info(self, "Flutter", "Pick a device first (the refresh button looks for new ones).")
            return
        try:
            tool_args = shlex.split(self._args_edit.text())
        except ValueError as e:
            dialogs.error(self, "Flutter", f"Extra args are not valid: {e}")
            return
        flavor = self._flavor().strip()
        settings = FlutterRunSettings(
            cwd=self._cwd,
            target=self._target_edit.text().strip() or "lib/main.dart",
            mode=self._mode(),
            device_id=device,
            flavor=flavor,
            tool_args=tool_args,
            app_args=self._app_args,
            env=self._env,
        )
        has_flavor = bool(flavor) or any(a == "--flavor" or a.startswith("--flavor=") for a in tool_args)
        if self._flavors and not has_flavor:
            dialogs.warn(
                self, "Flutter",
                "This project defines flavors (" + ", ".join(self._flavors) + ") and the build fails "
                "without one.\n\nPick one in Flavor, or choose a launch.json configuration.",
            )
            return
        config = self._configs.get(self._config_box.currentText())
        if config and config.data.get("preLaunchTask"):
            self._log(f'preLaunchTask "{config.data["preLaunchTask"]}" is skipped for Flutter runs.', "note")

        session = FlutterSession(self._flutter, settings)
        try:
            session.start()
        except OSError as e:
            dialogs.error(self, "Flutter", f"Could not start flutter: {e}")
            return
        self._session = session
        self._toggle_reset()
        self._log(f"$ {shlex.join(session.command_line())}", "note")
        self._stopping = False
        self._busy_since = time.monotonic()
        self._set_status("Starting…")
        self._save()
        self._update_controls()

    def _stop(self) -> None:
        if self._busy():
            self._stopping = True
            self._busy_since = time.monotonic()
            self._set_status("Stopping…")
            self._session.stop()
            self._update_controls()

    def _hot_reload(self) -> None:
        self._restart(False)

    def _hot_restart(self) -> None:
        self._restart(True)

    def _restart(self, full: bool) -> None:
        session = self._session
        if not session or not session.started or self._mode() != "debug":
            return
        what = "Hot restart" if full else "Hot reload"
        self._set_status(f"{what}…")
        started = time.monotonic()

        def done(error: Optional[str]) -> None:
            if error:
                self._log(f"{what} failed: {error}", "error")
            else:
                self._log(f"{what} done in {int((time.monotonic() - started) * 1000)} ms", "note")
            self._set_status("Running")

        (session.restart if full else session.reload)(done)

    def _toggle(self, toggle) -> None:
        btn = self._toggle_buttons[toggle.method]
        session = self._session
        wanted = btn.isChecked()
        if not session or not session.started:
            btn.setChecked(not wanted)
            return

        def done(is_on: Optional[bool], error: Optional[str]) -> None:
            if error:
                self._log(f"{toggle.label} failed: {error}", "error")
                btn.setChecked(not wanted)
            else:
                btn.setChecked(bool(is_on))

        session.set_extension(toggle, wanted, done)

    def _toggle_reset(self) -> None:
        for btn in self._toggle_buttons.values():
            btn.setChecked(False)

    # -- polling --

    def _tick(self) -> None:
        try:
            while True:
                self._devices_loaded(*self._device_results.get_nowait())
        except queue.Empty:
            pass
        session = self._session
        if session:
            for event in session.poll():
                self._handle(event)
        self._refresh_status()

    def _handle(self, event) -> None:
        if event.kind in ("log", "error"):
            self._log(event.text, event.kind)
        elif event.kind == "status":
            if event.text:
                self._set_status(event.text)
                self._update_controls()
        elif event.kind == "state":
            self._update_controls()
        elif event.kind == "exit":
            self._log(f"flutter exited with code {event.text}", "note")
            self._session = None
            self._stopping = False
            self._toggle_reset()
            self._set_status("Stopped")
            self._refresh_btn.setEnabled(True)
            self._update_controls()

    def _update_controls(self) -> None:
        session = self._session
        busy = self._busy()
        started = bool(session and session.started)
        mode = self._mode()
        self._run_btn.setEnabled(not busy)
        self._stop_btn.setEnabled(busy)
        reloadable = started and mode == "debug"
        self._reload_btn.setEnabled(reloadable)
        self._restart_btn.setEnabled(reloadable)
        for tg in TOGGLES:
            self._toggle_buttons[tg.method].setEnabled(started and mode in tg.modes)
        working = busy and (not started or self._stopping)
        if working:
            self._progress.start()
        else:
            self._progress.stop()
        self._lamp.set_state("busy" if working else ("running" if started else "idle"))
        for w in self._form_widgets:
            w.setEnabled(not busy)

    def _set_status(self, text: str) -> None:
        self._status_text = text
        self._refresh_status()

    def _refresh_status(self) -> None:
        """Status text; while building or stopping it also shows the elapsed time."""
        text = self._status_text
        session = self._session
        if session and session.running and (not session.started or self._stopping):
            seconds = int(time.monotonic() - self._busy_since)
            text = f"{text.rstrip('.…')}…  {seconds // 60}:{seconds % 60:02d}"
        elif session and session.started and self._mode() != "debug":
            text += f"  ({self._mode()} mode: no hot reload/restart, run in debug)"
        if self._status.text() != text:
            self._status.setText(text)

    # -- log --

    def _log(self, text: str, tag: str = "") -> None:
        box = self._log_text
        bar = box.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 2
        fmt = QTextCharFormat()
        if tag == "error":
            fmt.setForeground(t("red"))
        elif tag == "note":
            fmt.setForeground(t("ink_dim"))
        cursor = QTextCursor(box.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not box.document().isEmpty():
            cursor.insertBlock()
        cursor.insertText(text, fmt)
        if at_bottom:
            bar.setValue(bar.maximum())

    def _clear_log(self) -> None:
        self._log_text.clear()

    # -- closing --

    def _stop_and_wait(self) -> None:
        """Stop the app and wait (briefly) for flutter to exit so no process is left behind."""
        session = self._session
        if not session or not session.running:
            return
        session.stop()
        deadline = time.monotonic() + STOP_GRACE_SECONDS + 2
        while session.running and time.monotonic() < deadline:
            session.poll()
            time.sleep(0.05)
        if session.running:
            session.kill()

    def closeEvent(self, event) -> None:
        if self._busy():
            if not dialogs.confirm(self, "Flutter", "Stop the running app and close this window?", "Stop and close"):
                event.ignore()
                return
            self._set_status("Stopping…")
            QApplication.processEvents()
            self._stop_and_wait()
        self._timer.stop()
        self._save()
        self._windows.pop(self._folder, None)
        try:
            Theme.get().changed.disconnect(self._retheme)
        except (RuntimeError, TypeError):
            pass
        self.deleteLater()
        event.accept()
