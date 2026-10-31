"""Window that runs a Flutter app like VS Code: pick devices and mode, hot reload/restart, toggles.

The runs themselves belong to the RunManager: they keep going in the background when this
window is closed, and the window shows them again when it is reopened.
"""

from __future__ import annotations

import shlex
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from services.flutter_runner import TOGGLES, FlutterDevice, detect_flavors, find_flutter
from services.project_service import ProjectService
from services.vscode_launch import FLUTTER_MODES, FlutterRunSettings, LaunchError, LaunchFile, flutter_settings
from ui import dialogs
from ui.icon_loader import load_icon
from ui.log_view import Line, LogView
from ui.run_manager import CUSTOM, NOT_FOUND, RunManager, flavor_problem, flutter_configs, saved_run
from ui.theme import apply_title_bar
from ui.widgets import Combo, DymoLabel, FoamPanel, IconWell, ScanBar, StatusLamp, ToolSlot

STATUS_MS = 250


def _caps(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("role", "caps")
    return label


def rename_device(parent: QWidget, device_id: str, model: str) -> None:
    """Ask for a name that tells this device apart (two phones of the same model, say)."""
    manager = RunManager.get()
    name = dialogs.ask_text(
        parent, "Name this device",
        f"A name to tell this device apart, shown everywhere instead of “{model or device_id}”.\n"
        f"Device id: {device_id}\n\nLeave it empty to use the model name again.",
        manager.device_name(device_id), ok_text="Save name",
    )
    if name is not None:
        manager.rename_device(device_id, name)


class _DeviceRow(QWidget):
    toggled = Signal(str, bool)
    rename = Signal(str)

    def __init__(self, device: FlutterDevice):
        super().__init__()
        self.device = device
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.check = QCheckBox()
        self.check.toggled.connect(lambda on: self.toggled.emit(device.id, on))
        row.addWidget(self.check)
        self.detail = QLabel()
        self.detail.setProperty("role", "mono")
        row.addWidget(self.detail, 1)
        tag = ToolSlot("", "tag", variant="quiet", compact=True, tooltip="Name this device")
        tag.clicked.connect(lambda: self.rename.emit(device.id))
        row.addWidget(tag)
        self.refresh()

    def refresh(self) -> None:
        d = self.device
        manager = RunManager.get()
        name = manager.device_name(d.id)
        self.check.setText(name or d.name)
        kind = "emulator" if d.emulator else d.platform
        bits = ([d.name] if name else []) + ([kind] if kind else []) + [d.id]
        self.detail.setText("  ·  ".join(bits))
        self.setToolTip(f"{d.name} ({kind or 'device'})  ·  {d.id}")


class _DeviceList(QScrollArea):
    """Tick the devices to run on; each can be given a name."""

    changed = Signal()
    rename = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        self._layout = QVBoxLayout(holder)
        self._layout.setContentsMargins(2, 4, 2, 4)
        self._layout.setSpacing(4)
        self.setWidget(holder)
        self._rows: dict[str, _DeviceRow] = {}
        self._placeholder = QLabel()
        self._placeholder.setProperty("role", "dim")
        self._layout.addWidget(self._placeholder)
        self._layout.addStretch()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._fit()

    def set_placeholder(self, text: str) -> None:
        self._placeholder.setText(text)
        self._placeholder.setVisible(bool(text))
        self._fit()

    def set_devices(self, devices: list[FlutterDevice], checked: set[str]) -> None:
        for row in self._rows.values():
            row.deleteLater()
        self._rows = {}
        for i, d in enumerate(devices):
            row = _DeviceRow(d)
            row.check.setChecked(d.id in checked)
            row.toggled.connect(lambda *_: self.changed.emit())
            row.rename.connect(self.rename)
            self._layout.insertWidget(i, row)
            self._rows[d.id] = row
        self._fit()

    def refresh_names(self) -> None:
        for row in self._rows.values():
            row.refresh()

    def device(self, device_id: str) -> Optional[FlutterDevice]:
        row = self._rows.get(device_id)
        return row.device if row else None

    def devices(self) -> list[FlutterDevice]:
        return [r.device for r in self._rows.values()]

    def checked(self) -> list[FlutterDevice]:
        return [r.device for r in self._rows.values() if r.check.isChecked()]

    def lock(self, busy_ids: set[str]) -> None:
        """Devices that are running stay ticked until they stop."""
        for device_id, row in self._rows.items():
            busy = device_id in busy_ids
            if busy and not row.check.isChecked():
                row.check.setChecked(True)
            row.check.setEnabled(not busy)

    def _fit(self) -> None:
        rows = max(1, len(self._rows) + (1 if self._placeholder.isVisible() else 0))
        self.setFixedHeight(min(rows, 4) * 34 + 8)


class FlutterRunWindow(QWidget):
    """One window per folder; opening it again just brings it to the front."""

    _windows: dict[str, "FlutterRunWindow"] = {}

    @classmethod
    def open(
        cls, parent: Optional[QWidget], folder: str, launch: Optional[LaunchFile],
        config_name: Optional[str] = None, name: str = "", icon_path: Optional[str] = None,
        note: Optional[str] = None,
    ) -> "FlutterRunWindow":
        """Open (or bring forward) the folder's window. note: a message to show in its log.

        name / icon_path identify the project in the window's header and taskbar icon.
        """
        window = cls._windows.get(folder)
        if window is None:
            window = cls(folder, launch, config_name, name, icon_path)
            cls._windows[folder] = window
            window.show()
        else:
            window.showNormal()
            window.raise_()
            window.activateWindow()
            window.select_config(config_name)
        if note:
            window.note(note, "error")
        return window

    @classmethod
    def save_all(cls) -> None:
        for window in list(cls._windows.values()):
            window._save()

    def __init__(
        self, folder: str, launch: Optional[LaunchFile], config_name: Optional[str],
        name: str = "", icon_path: Optional[str] = None,
    ):
        super().__init__(None, Qt.WindowType.Window)
        self.setObjectName("FlutterRunWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._manager = RunManager.get()
        self._project_name = name
        self._icon_path = icon_path
        self._folder = folder
        self._flavors = detect_flavors(folder)
        self._launch = launch
        self._configs = flutter_configs(launch)
        self._wanted: set[str] = set()  # Device ids to tick once devices are listed
        self._toggle_buttons: dict[str, ToolSlot] = {}
        self._chips: dict[str, ToolSlot] = {}
        self._selected: Optional[str] = None  # Run whose log and toggles are shown
        self._notes: list[Line] = []  # Shown in the log while no run exists
        self._looking = False
        self._cwd = folder  # Where flutter runs; a launch.json "cwd" can point at a sub-folder
        self._env: dict = {}
        self._app_args: list[str] = []
        self._loading = True  # Don't save while restoring

        self.setWindowTitle(f"{name} - Flutter" if name else f"Flutter - {folder}")
        self.resize(960, 940)
        self.setMinimumSize(740, 660)
        big = load_icon(icon_path, 64)
        if big:
            self.setWindowIcon(QIcon(big))  # Taskbar / title bar, to tell the windows apart
        self._build()
        QShortcut(QKeySequence("Ctrl+R"), self, lambda: self._manager.reload_folder(self._folder, False))
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, lambda: self._manager.reload_folder(self._folder, True))

        self._save_timer = QTimer(self, singleShot=True, interval=400)
        self._save_timer.timeout.connect(self._save)
        self._status_timer = QTimer(self, interval=STATUS_MS)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start()

        self._restore(config_name)
        self._loading = False
        self._manager.changed.connect(self._sync)
        self._manager.logged.connect(self._on_logged)
        self._manager.log_cleared.connect(self._on_cleared)
        self._sync()
        self._refresh_devices()

        if not find_flutter():
            self.note(NOT_FOUND, "error")

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

        self._device_list = _DeviceList()
        self._device_list.changed.connect(self._devices_ticked)
        self._device_list.rename.connect(self._rename)
        self._refresh_btn = ToolSlot("", "restart", tooltip="Look for devices again")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        form.addWidget(_caps("Devices"), 1, 0, Qt.AlignmentFlag.AlignTop)
        form.addWidget(self._device_list, 1, 1)
        form.addWidget(self._refresh_btn, 1, 2, Qt.AlignmentFlag.AlignTop)

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
            self._config_box, *self._mode_buttons.values(), self._target_edit, self._flavor_edit, self._args_edit,
        ]
        root.addWidget(form_panel)

        # Controls (every device of this folder)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self._run_btn = ToolSlot("Run", "play", variant="primary", tooltip="Run on the ticked devices")
        self._run_btn.reserve("Run · 9")
        self._run_btn.clicked.connect(self._run)
        self._stop_btn = ToolSlot("Stop", "stop", variant="danger", tooltip="Stop on every device")
        self._stop_btn.clicked.connect(lambda: self._manager.stop_folder(self._folder))
        self._reload_btn = ToolSlot("Hot reload", "bolt", tooltip="Hot reload every device (Ctrl+R)")
        self._reload_btn.clicked.connect(lambda: self._manager.reload_folder(self._folder, False))
        self._restart_btn = ToolSlot("Hot restart", "restart", tooltip="Hot restart every device (Ctrl+Shift+R)")
        self._restart_btn.clicked.connect(lambda: self._manager.reload_folder(self._folder, True))
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

        # Which device's toggles and log are shown (only with more than one)
        self._chip_row = QWidget()
        chips = QHBoxLayout(self._chip_row)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(4)
        chips.addWidget(_caps("Device"))
        chips.addSpacing(6)
        self._chip_layout = QHBoxLayout()
        self._chip_layout.setSpacing(4)
        chips.addLayout(self._chip_layout)
        chips.addStretch()
        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)
        self._chip_row.hide()
        root.addWidget(self._chip_row)

        # Service extension toggles (the device shown)
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
        self._log_caps = _caps("flutter run log")
        log_head.addWidget(self._log_caps)
        log_head.addStretch()
        clear = ToolSlot("Clear log", "erase", variant="quiet", compact=True)
        clear.clicked.connect(self._clear_log)
        log_head.addWidget(clear)
        root.addLayout(log_head)
        self._log = LogView()
        root.addWidget(self._log, 1)

    def showEvent(self, event) -> None:
        apply_title_bar(self)
        super().showEvent(event)

    # -- saved settings --

    def _mode(self) -> str:
        return next((m for m, b in self._mode_buttons.items() if b.isChecked()), "debug")

    def _set_mode(self, mode: str) -> None:
        self._mode_buttons.get(mode, self._mode_buttons["debug"]).setChecked(True)

    def _on_mode_picked(self, mode: str) -> None:
        self._set_mode(mode)
        self._schedule_save()

    def _flavor(self) -> str:
        return self._flavor_line.text()

    def _restore(self, config_name: Optional[str]) -> None:
        """Start from the saved settings; a config picked from the menu overrides them."""
        try:
            saved = saved_run(self._folder, self._launch, config_name)
        except LaunchError as e:
            dialogs.error(self, "launch.json", str(e))
            return
        self._config_box.setCurrentText(saved.config)
        self._fill(saved.settings, saved.args)
        self._wanted = set(saved.devices)

    def _fill(self, settings: FlutterRunSettings, args: str) -> None:
        self._cwd = settings.cwd
        self._env = settings.env
        self._app_args = settings.app_args
        self._target_edit.setText(settings.target)
        self._set_mode(settings.mode)
        self._flavor_line.setText(settings.flavor)
        self._args_edit.setText(args)

    def _schedule_save(self, *_) -> None:
        if not self._loading:
            self._save_timer.start()

    def _save(self) -> None:
        self._save_timer.stop()
        devices = [d.id for d in self._device_list.checked()] if self._device_list.devices() else sorted(self._wanted)
        ProjectService.set_flutter_run(self._folder, {
            "config": self._config_box.currentText(),
            "devices": devices,
            "device": devices[0] if devices else None,  # Read by older versions
            "mode": self._mode(),
            "target": self._target_edit.text(),
            "flavor": self._flavor(),
            "args": self._args_edit.text(),
        })

    # -- configuration and devices --

    def select_config(self, name: Optional[str]) -> None:
        if name in self._configs and not self._manager.active_runs(self._folder):
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
        self._fill(settings, shlex.join(settings.tool_args))
        if settings.device_id:
            self._wanted = {settings.device_id}
            if self._device_list.devices():
                self._device_list.set_devices(self._device_list.devices(), self._wanted)
        self._sync()

    def _refresh_devices(self) -> None:
        if self._looking or not find_flutter():
            return
        self._looking = True
        self._refresh_btn.setEnabled(False)
        self._device_list.set_placeholder("Looking for devices…")
        self._manager.list_devices_async(self._devices_loaded)

    def _devices_loaded(self, devices: Optional[list[FlutterDevice]], error: Optional[str]) -> None:
        self._looking = False
        self._refresh_btn.setEnabled(True)
        if error:
            self._device_list.set_placeholder("Could not list devices")
            self.note(error, "error")
            return
        if self._device_list.devices():
            self._wanted = {d.id for d in self._device_list.checked()}
        devices = list(devices or [])
        known = {d.id for d in devices}
        for run in self._manager.active_runs(self._folder):  # A running device stays listed
            if run.device_id not in known:
                devices.append(FlutterDevice(run.device_id, run.model, ""))
        if not devices:
            self._device_list.set_devices([], set())
            self._device_list.set_placeholder("No devices found. Connect a phone with USB debugging, or start an emulator.")
        else:
            self._device_list.set_placeholder("")
            if not self._wanted & {d.id for d in devices}:
                self._wanted.add(devices[0].id)
            self._device_list.set_devices(devices, self._wanted)
        self._sync()

    def _devices_ticked(self) -> None:
        self._wanted = {d.id for d in self._device_list.checked()}
        self._schedule_save()
        self._update_controls()

    def _rename(self, device_id: str) -> None:
        device = self._device_list.device(device_id)
        rename_device(self, device_id, device.name if device else "")

    # -- running --

    def _run(self) -> None:
        if not find_flutter():
            dialogs.error(self, "Flutter", NOT_FOUND)
            return
        busy = {r.device_id for r in self._manager.active_runs(self._folder)}
        devices = [d for d in self._device_list.checked() if d.id not in busy]
        if not devices:
            dialogs.info(self, "Flutter", "Tick one or more devices first (the refresh button looks for new ones).")
            return
        try:
            tool_args = shlex.split(self._args_edit.text())
        except ValueError as e:
            dialogs.error(self, "Flutter", f"Extra args are not valid: {e}")
            return
        settings = FlutterRunSettings(
            cwd=self._cwd,
            target=self._target_edit.text().strip() or "lib/main.dart",
            mode=self._mode(),
            flavor=self._flavor().strip(),
            tool_args=tool_args,
            app_args=self._app_args,
            env=self._env,
        )
        problem = flavor_problem(self._folder, settings)
        if problem:
            dialogs.warn(self, "Flutter", problem)
            return
        self._save()
        error = self._manager.start(self._folder, settings, devices, self._project_name, self._icon_path)
        if error:
            dialogs.error(self, "Flutter", error)
        config = self._configs.get(self._config_box.currentText())
        first = next((r for r in self._manager.runs(self._folder) if r.device_id == devices[0].id), None)
        if first:
            self._select(first.id)
            if config and config.data.get("preLaunchTask"):
                self._manager.note(first.id, f'preLaunchTask "{config.data["preLaunchTask"]}" is skipped for Flutter runs.')

    def _toggle(self, toggle) -> None:
        btn = self._toggle_buttons[toggle.method]
        run = self._manager.run(self._selected)
        if run is None or not run.started:
            btn.setChecked(not btn.isChecked())
            return
        self._manager.set_toggle(run.id, toggle, btn.isChecked())

    # -- following the manager --

    def _select(self, rid: Optional[str]) -> None:
        if rid == self._selected:
            return
        self._selected = rid
        run = self._manager.run(rid)
        self._log.set_lines(run.log if run else self._notes)
        chip = self._chips.get(rid) if rid else None
        if chip:
            chip.setChecked(True)
        self._sync()

    def _sync(self) -> None:
        """Bring the chips, toggles, buttons and status up to date with the folder's runs."""
        runs = self._manager.runs(self._folder)
        ids = [r.id for r in runs]
        if self._selected not in ids:
            pick = next((r.id for r in runs if r.active), ids[0] if ids else None)
            if pick != self._selected:
                self._select(pick)
                return
        if list(self._chips) != ids:
            for chip in self._chips.values():
                self._chip_group.removeButton(chip)
                chip.deleteLater()
            self._chips = {}
            for run in runs:
                chip = ToolSlot(run.label, compact=True)
                chip.setCheckable(True)
                chip.clicked.connect(lambda _=False, rid=run.id: self._select(rid))
                self._chip_group.addButton(chip)
                self._chip_layout.addWidget(chip)
                self._chips[run.id] = chip
            if self._selected in self._chips:
                self._chips[self._selected].setChecked(True)
        for run in runs:
            chip = self._chips[run.id]
            if chip.text() != run.label:
                chip.setText(run.label)
            chip.setToolTip(f"{run.label}: {run.status_text()}")
        self._chip_row.setVisible(len(runs) > 1)
        selected = self._manager.run(self._selected)
        self._log_caps.setText(("flutter run log · " + selected.label).upper() if selected else "FLUTTER RUN LOG")
        self._device_list.refresh_names()
        self._update_controls()

    def _on_logged(self, rid: str, lines) -> None:
        if rid == self._selected:
            self._log.append_lines(lines)

    def _on_cleared(self, rid: str) -> None:
        if rid == self._selected:
            self._log.clear()

    def _clear_log(self) -> None:
        if self._selected:
            self._manager.clear_log(self._selected)
        else:
            self._notes.clear()
            self._log.clear()

    def note(self, text: str, kind: str = "note") -> None:
        """A message in the log: the shown run's, or the window's own before anything ran."""
        if self._selected:
            self._manager.note(self._selected, text, kind)
        else:
            self._notes.append((text, kind))
            self._log.append_lines([(text, kind)])

    def _update_controls(self) -> None:
        active = self._manager.active_runs(self._folder)
        busy_ids = {r.device_id for r in active}
        self._device_list.lock(busy_ids)
        to_run = [d for d in self._device_list.checked() if d.id not in busy_ids]
        self._run_btn.setEnabled(bool(to_run) and bool(find_flutter()))
        self._run_btn.setText(f"Run · {len(to_run)}" if len(to_run) > 1 else "Run")
        self._stop_btn.setEnabled(any(not r.stopping for r in active))
        reloadable = any(r.reloadable for r in active)
        self._reload_btn.setEnabled(reloadable)
        self._restart_btn.setEnabled(reloadable)
        selected = self._manager.run(self._selected)
        for tg in TOGGLES:
            btn = self._toggle_buttons[tg.method]
            btn.setEnabled(bool(selected and selected.started and selected.mode in tg.modes))
            btn.setChecked(bool(selected and selected.toggles.get(tg.method)))
        for w in self._form_widgets:
            w.setEnabled(not active)
        self._refresh_status()

    def _refresh_status(self) -> None:
        """One device: its status and timer. Several: how many build, run and stop."""
        active = self._manager.active_runs(self._folder)
        selected = self._manager.run(self._selected)
        states = [r.state() for r in active]
        working = any(s in ("building", "stopping") for s in states)
        if len(active) == 1:
            text = active[0].status_text()
        elif active:
            parts = []
            for state, word in (("building", "building"), ("running", "running"), ("stopping", "stopping")):
                n = states.count(state)
                if n:
                    parts.append(f"{n} {word}")
            busy = [r for r in active if r.state() in ("building", "stopping")]
            text = " · ".join(parts)
            if busy:
                s = max(r.seconds() for r in busy)
                text += f"  {s // 60}:{s % 60:02d}"
        else:
            text = selected.status if selected else "Stopped"
        if self._status.text() != text:
            self._status.setText(text)
        if working:
            self._progress.start()
        else:
            self._progress.stop()
        failed = bool(selected and selected.failed and not active)
        self._lamp.set_state(
            "busy" if working else "running" if "running" in states else "error" if failed else "idle"
        )

    # -- closing --

    def closeEvent(self, event) -> None:
        """Closing only hides the view: running apps keep going (the Log sidebar still shows them)."""
        self._status_timer.stop()
        self._save()
        self._windows.pop(self._folder, None)
        for signal, slot in (
            (self._manager.changed, self._sync), (self._manager.logged, self._on_logged),
            (self._manager.log_cleared, self._on_cleared),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self.deleteLater()
        event.accept()

