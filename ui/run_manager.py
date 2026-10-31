"""Flutter runs that live in the background: one per folder and device, each with its own log.

The Flutter window and the log sidebar are views of these runs. Closing a view never stops an
app; quitting Project Manager does.
"""

from __future__ import annotations

import dataclasses
import os
import queue
import shlex
import threading
import time
from collections import deque
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from services.flutter_runner import (
    STOP_GRACE_SECONDS, FlutterDevice, FlutterError, FlutterSession, Toggle, detect_flavors,
    find_flutter, list_devices,
)
from services.project_service import ProjectService
from services.vscode_launch import (
    FLUTTER_MODES, FlutterRunSettings, LaunchConfig, LaunchError, LaunchFile, flutter_settings,
)
from ui.log_view import MAX_LOG_LINES, Line

POLL_MS = 100
CUSTOM = "Custom"
NOT_FOUND = "Flutter was not found. Add flutter\\bin to PATH (or set FLUTTER_ROOT)."

DevicesCallback = Callable[[Optional[list[FlutterDevice]], Optional[str]], None]


# --- Saved settings ---------------------------------------------------------------------------

def flutter_configs(launch: Optional[LaunchFile]) -> dict[str, LaunchConfig]:
    return {c.name: c for c in (launch.configs if launch else []) if c.kind == "flutter"}


@dataclasses.dataclass
class SavedRun:
    config: str  # A launch.json configuration name, or CUSTOM
    settings: FlutterRunSettings  # device_id is not used: devices says where to run
    args: str  # Extra `flutter run` arguments as typed
    devices: list[str]


def saved_run(folder: str, launch: Optional[LaunchFile], config_name: Optional[str] = None) -> SavedRun:
    """The folder's saved run: its launch.json configuration, then the fields the user changed.

    config_name (picked from the Launch menu) wins over the saved fields. Raises LaunchError.
    """
    saved = ProjectService.get_flutter_run(folder)
    configs = flutter_configs(launch)
    name = config_name or saved.get("config")
    if name in configs:
        settings = flutter_settings(folder, configs[name])
    else:
        name = CUSTOM
        settings = FlutterRunSettings(cwd=folder)
    args = shlex.join(settings.tool_args)
    if not config_name:
        settings.target = saved.get("target") or settings.target
        if saved.get("mode") in FLUTTER_MODES:
            settings.mode = saved["mode"]
        settings.flavor = saved.get("flavor", settings.flavor)
        args = saved.get("args", args)
    saved_devices = saved.get("devices") or ([saved["device"]] if saved.get("device") else [])
    if config_name and settings.device_id:
        devices = [settings.device_id]
    else:
        devices = list(saved_devices) or ([settings.device_id] if settings.device_id else [])
    return SavedRun(name, settings, args, devices)


def flavor_problem(folder: str, settings: FlutterRunSettings) -> Optional[str]:
    """A message if the project defines flavors and none is picked (the build would fail)."""
    flavors = detect_flavors(folder)
    has_flavor = bool(settings.flavor.strip()) or any(
        a == "--flavor" or a.startswith("--flavor=") for a in settings.tool_args
    )
    if flavors and not has_flavor:
        return (
            "This project defines flavors (" + ", ".join(flavors) + ") and the build fails without one.\n\n"
            "Pick one in Flavor, or choose a launch.json configuration."
        )
    return None


def run_id(folder: str, device_id: str) -> str:
    return f"{os.path.normcase(os.path.normpath(folder))}|{device_id}"


# --- One app on one device --------------------------------------------------------------------

class Run:
    """`flutter run` of one folder on one device, kept (with its log) after it stops."""

    def __init__(self, folder: str, device_id: str, model: str, name: str, icon_path: Optional[str]):
        self.id = run_id(folder, device_id)
        self.folder = folder
        self.device_id = device_id
        self.model = model
        self.name = name  # Project (and folder) name
        self.icon_path = icon_path
        self.session: Optional[FlutterSession] = None
        self.settings: Optional[FlutterRunSettings] = None
        self.log: deque[Line] = deque(maxlen=MAX_LOG_LINES)
        self.status = "Stopped"
        self.busy_since = time.monotonic()  # When the current build or stop began
        self.stopping = False
        self.failed = False  # Exited by itself with an error
        self.toggles: dict[str, bool] = {}  # Service extension method -> on

    @property
    def active(self) -> bool:
        return bool(self.session and self.session.running)

    @property
    def started(self) -> bool:
        return bool(self.session and self.session.started)

    @property
    def mode(self) -> str:
        return self.settings.mode if self.settings else "debug"

    @property
    def reloadable(self) -> bool:
        return self.started and self.mode == "debug" and not self.stopping

    def state(self) -> Optional[str]:
        """"building", "running", "stopping", or None when the app isn't running."""
        if not self.active:
            return None
        if self.stopping:
            return "stopping"
        return "running" if self.started else "building"

    def seconds(self) -> int:
        return int(time.monotonic() - self.busy_since)

    @property
    def label(self) -> str:
        return RunManager.get().device_label(self.device_id, self.model)

    @property
    def title(self) -> str:
        return f"{self.name} · {self.label}" if self.name else self.label

    def status_text(self) -> str:
        """Status with the elapsed time while building or stopping."""
        state = self.state()
        if state in ("building", "stopping"):
            s = self.seconds()
            return f"{self.status.rstrip('.…')}…  {s // 60}:{s % 60:02d}"
        if state == "running" and self.mode != "debug":
            return f"{self.status}  ({self.mode} mode: no hot reload)"
        return self.status


# --- The manager ------------------------------------------------------------------------------

class RunManager(QObject):
    """Every Flutter run in the program. Polls their output on the UI thread."""

    changed = Signal()  # A run was added or removed, or its state or status changed
    logged = Signal(str, object)  # run id, list of (text, kind) lines
    log_cleared = Signal(str)  # run id

    _instance: "RunManager | None" = None

    @classmethod
    def get(cls) -> "RunManager":
        if cls._instance is None:
            cls._instance = RunManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._runs: dict[str, Run] = {}
        self._names = ProjectService.get_device_names()
        self._results: queue.Queue = queue.Queue()  # (callback, devices, error) from device lookups
        self._lookups = 0  # Device lookups in flight
        self._pending: dict[str, float] = {}  # folder -> when its quick start began looking for devices
        self._timer = QTimer(self, interval=POLL_MS)
        self._timer.timeout.connect(self._tick)

    # -- queries --

    def runs(self, folder: Optional[str] = None) -> list[Run]:
        if folder is None:
            return list(self._runs.values())
        key = run_id(folder, "")
        return [r for r in self._runs.values() if r.id.startswith(key)]

    def run(self, rid: Optional[str]) -> Optional[Run]:
        return self._runs.get(rid) if rid else None

    def active_runs(self, folder: Optional[str] = None) -> list[Run]:
        return [r for r in self.runs(folder) if r.active]

    def folder_state(self, folder: str) -> tuple[Optional[str], int, int]:
        """(state, seconds busy, devices running) across the folder's runs.

        state is "building" (also while a quick start looks for devices), "stopping",
        "running" or None.
        """
        runs = self.active_runs(folder)
        pending = self._pending.get(folder)
        building = [r for r in runs if r.state() == "building"]
        stopping = [r for r in runs if r.state() == "stopping"]
        running = [r for r in runs if r.state() == "running"]
        if building or pending is not None:
            since = min([r.busy_since for r in building] + ([pending] if pending is not None else []))
            return "building", int(time.monotonic() - since), len(running)
        if stopping:
            return "stopping", max(r.seconds() for r in stopping), len(running)
        if running:
            return "running", 0, len(running)
        return None, 0, 0

    def device_label(self, device_id: str, model: str = "") -> str:
        """The name the user gave the device, else its model name, else its id."""
        return self._names.get(device_id) or model or device_id

    def device_name(self, device_id: str) -> str:
        """Only the name the user gave the device ("" if none)."""
        return self._names.get(device_id, "")

    def rename_device(self, device_id: str, name: str) -> None:
        ProjectService.set_device_name(device_id, name)
        self._names = ProjectService.get_device_names()
        self.changed.emit()

    # -- devices --

    def list_devices_async(self, done: DevicesCallback) -> None:
        """List devices on a thread; done(devices, error) is called on the UI thread."""
        flutter = find_flutter()
        if not flutter:
            done(None, NOT_FOUND)
            return

        def work():
            try:
                self._results.put((done, list_devices(flutter), None))
            except FlutterError as e:
                self._results.put((done, None, str(e)))

        self._lookups += 1
        threading.Thread(target=work, daemon=True).start()
        self._timer.start()

    # -- running --

    def start(self, folder: str, settings: FlutterRunSettings, devices: list[FlutterDevice],
              name: str = "", icon_path: Optional[str] = None) -> Optional[str]:
        """Run on each device that isn't running this folder yet. Returns an error message or None."""
        flutter = find_flutter()
        if not flutter:
            return NOT_FOUND
        error = None
        for device in devices:
            rid = run_id(folder, device.id)
            run = self._runs.get(rid)
            if run is None:
                run = Run(folder, device.id, device.name, name, icon_path)
                self._runs[rid] = run
            else:
                run.model, run.name, run.icon_path = device.name, name or run.name, icon_path or run.icon_path
            if run.active:
                continue
            error = self._launch(run, flutter, dataclasses.replace(
                settings, device_id=device.id, tool_args=list(settings.tool_args),
                app_args=list(settings.app_args), env=dict(settings.env),
            )) or error
        self.changed.emit()
        return error

    def _launch(self, run: Run, flutter: str, settings: FlutterRunSettings) -> Optional[str]:
        session = FlutterSession(flutter, settings)
        try:
            session.start()
        except OSError as e:
            self._log(run, f"Could not start flutter: {e}", "error")
            return f"Could not start flutter: {e}"
        run.session = session
        run.settings = settings
        run.toggles = {}
        run.stopping = False
        run.failed = False
        run.busy_since = time.monotonic()
        run.status = "Starting…"
        self._log(run, f"$ {shlex.join(session.command_line())}", "note")
        self._timer.start()
        return None

    def run_again(self, rid: str) -> Optional[str]:
        """Start a stopped run again with the settings it last ran with."""
        run = self._runs.get(rid)
        if run is None or run.active or run.settings is None:
            return None
        flutter = find_flutter()
        if not flutter:
            return NOT_FOUND
        error = self._launch(run, flutter, run.settings)
        self.changed.emit()
        return error

    def quick_start(self, folder: str, launch: Optional[LaunchFile], name: str, icon_path: Optional[str],
                    on_problem: Callable[[str], None]) -> None:
        """Run in the background on the saved devices. on_problem(message) when it can't.

        Problems: no Flutter, no saved device, none of them connected, a flavor is needed, ...
        """
        if self.active_runs(folder) or folder in self._pending:
            return
        if not find_flutter():
            on_problem(NOT_FOUND)
            return
        try:
            saved = saved_run(folder, launch)
            saved.settings.tool_args = shlex.split(saved.args)
        except LaunchError as e:
            on_problem(f"launch.json: {e}")
            return
        except ValueError as e:
            on_problem(f"The saved extra args are not valid: {e}")
            return
        if not saved.devices:
            on_problem("Quick start: no device saved yet. Pick one or more devices and press Run once.")
            return
        problem = flavor_problem(folder, saved.settings)
        if problem:
            on_problem(problem)
            return

        def listed(devices: Optional[list[FlutterDevice]], error: Optional[str]) -> None:
            self._pending.pop(folder, None)
            if error:
                self.changed.emit()
                on_problem(error)
                return
            by_id = {d.id: d for d in devices or []}
            found = [by_id[i] for i in saved.devices if i in by_id]
            missing = [self.device_label(i) for i in saved.devices if i not in by_id]
            if not found:
                self.changed.emit()
                on_problem(
                    "Quick start: the saved device" + ("s are" if len(missing) > 1 else " is")
                    + " not connected (" + ", ".join(missing) + "). Pick another and press Run."
                )
                return
            error = self.start(folder, saved.settings, found, name, icon_path)
            if error:
                on_problem(error)
            elif missing:
                first = self._runs[run_id(folder, found[0].id)]
                self._log(first, "Not connected, skipped: " + ", ".join(missing), "note")

        self._pending[folder] = time.monotonic()
        self.changed.emit()
        self.list_devices_async(listed)

    def stop(self, rid: str) -> None:
        run = self._runs.get(rid)
        if run is None or not run.active or run.stopping:
            return
        run.stopping = True
        run.busy_since = time.monotonic()
        run.status = "Stopping…"
        run.session.stop()
        self.changed.emit()

    def stop_folder(self, folder: str) -> None:
        for run in self.active_runs(folder):
            self.stop(run.id)

    def reload(self, rid: str, full: bool) -> None:
        """Hot reload (or hot restart with full) one run."""
        run = self._runs.get(rid)
        if run is None or not run.reloadable:
            return
        what = "Hot restart" if full else "Hot reload"
        run.status = f"{what}…"
        started = time.monotonic()
        session = run.session

        def done(error: Optional[str]) -> None:
            if error:
                self._log(run, f"{what} failed: {error}", "error")
            else:
                self._log(run, f"{what} done in {int((time.monotonic() - started) * 1000)} ms", "note")
            if run.session is session and run.started:
                run.status = "Running"
            self.changed.emit()

        (session.restart if full else session.reload)(done)
        self.changed.emit()

    def reload_folder(self, folder: str, full: bool) -> None:
        for run in self.active_runs(folder):
            self.reload(run.id, full)

    def set_toggle(self, rid: str, toggle: Toggle, on: bool) -> None:
        """Turn a service extension on or off for one run."""
        run = self._runs.get(rid)
        if run is None or not run.started:
            return
        session = run.session

        def done(is_on: Optional[bool], error: Optional[str]) -> None:
            if error:
                self._log(run, f"{toggle.label} failed: {error}", "error")
            elif run.session is session:
                run.toggles[toggle.method] = bool(is_on)
            self.changed.emit()

        run.toggles[toggle.method] = on  # Show it right away; corrected if it fails
        session.set_extension(toggle, on, done)
        self.changed.emit()

    def clear_log(self, rid: str) -> None:
        run = self._runs.get(rid)
        if run is not None:
            run.log.clear()
            self.log_cleared.emit(rid)

    def dismiss(self, rid: str) -> None:
        """Forget a stopped run and its log."""
        run = self._runs.get(rid)
        if run is not None and not run.active:
            del self._runs[rid]
            self.changed.emit()

    def note(self, rid: str, text: str, kind: str = "note") -> None:
        run = self._runs.get(rid)
        if run is not None:
            self._log(run, text, kind)

    def _log(self, run: Run, text: str, kind: str) -> None:
        run.log.append((text, kind))
        self.logged.emit(run.id, [(text, kind)])

    # -- polling --

    def _tick(self) -> None:
        while True:
            try:
                done, devices, error = self._results.get_nowait()
            except queue.Empty:
                break
            self._lookups -= 1
            try:
                done(devices, error)
            except RuntimeError:
                pass  # The view that asked was closed meanwhile
        dirty = False
        for run in list(self._runs.values()):
            session = run.session
            if session is None:
                continue
            lines: list[Line] = []
            for event in session.poll():
                if event.kind in ("log", "error"):
                    lines.append((event.text, event.kind))
                elif event.kind == "status":
                    if event.text:
                        run.status = event.text
                        dirty = True
                elif event.kind == "state":
                    dirty = True
                elif event.kind == "exit":
                    code = int(event.text) if event.text.lstrip("-").isdigit() else -1
                    run.failed = code != 0 and not run.stopping
                    run.session = None
                    run.stopping = False
                    run.toggles = {}
                    run.status = f"Exited with code {code}" if run.failed else "Stopped"
                    lines.append((f"flutter exited with code {code}", "note"))
                    dirty = True
            if lines:
                run.log.extend(lines)
                self.logged.emit(run.id, lines)
        if dirty:
            self.changed.emit()
        if not self._lookups and not self.active_runs():
            self._timer.stop()

    # -- quitting --

    def shutdown_all(self) -> None:
        """Stop every app and wait (briefly) so no `flutter run` is left behind."""
        sessions = [r.session for r in self.active_runs()]
        for s in sessions:
            s.stop()
        deadline = time.monotonic() + STOP_GRACE_SECONDS + 2
        while any(s.running for s in sessions) and time.monotonic() < deadline:
            for s in sessions:
                if s.running:
                    s.poll()
            time.sleep(0.05)
        for s in sessions:
            if s.running:
                s.kill()
