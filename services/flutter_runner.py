"""Run `flutter run --machine` and drive it like VS Code: hot reload/restart and service extensions."""

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from services.vscode_launch import FlutterRunSettings

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

STOP_GRACE_SECONDS = 5  # After app.stop, the process tree is killed if it hasn't exited by then


class FlutterError(Exception):
    """Flutter is missing or could not list devices."""


def find_flutter() -> Optional[str]:
    """First flutter on PATH, falling back to FLUTTER_ROOT."""
    found = shutil.which("flutter")
    if found:
        return found
    root = os.environ.get("FLUTTER_ROOT")
    if root:
        exe = os.path.join(root, "bin", "flutter.bat" if os.name == "nt" else "flutter")
        if os.path.isfile(exe):
            return exe
    return None


def _clean_env(extra: Optional[dict] = None) -> dict:
    """The current environment plus the launch configuration's env."""
    env = dict(os.environ)
    env.update(extra or {})
    return env


def detect_flavors(folder: str) -> list[str]:
    """Names inside productFlavors { ... } of android/app/build.gradle(.kts). Empty if none."""
    for name in ("build.gradle", "build.gradle.kts"):
        try:
            text = open(os.path.join(folder, "android", "app", name), encoding="utf-8-sig").read()
        except OSError:
            continue
        text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.DOTALL)
        start = re.search(r"productFlavors\s*\{", text)
        if not start:
            continue
        flavors, depth, i = [], 1, start.end()
        block_start = i
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[block_start:i - 1]
        # Top-level entries only: `dev {`, `create("dev") {`, `register("dev") {`, `getByName("dev") {`
        level, pos = 0, 0
        for m in re.finditer(r"[{}]", body):
            if level == 0:
                head = body[pos:m.start()].strip().splitlines()[-1:] or [""]
                found = re.search(r"""(?:create|register|maybeCreate)\s*\(\s*["'](\w+)["']|^(\w+)$""", head[0].strip())
                if m.group() == "{" and found:
                    flavors.append(found.group(1) or found.group(2))
            level += 1 if m.group() == "{" else -1
            pos = m.end()
        if flavors:
            return flavors
    return []


@dataclass
class FlutterDevice:
    id: str
    name: str
    platform: str  # targetPlatform, e.g. "android-arm64", "windows-x64", "web-javascript"
    emulator: bool = False

    def display_name(self) -> str:
        kind = "emulator" if self.emulator else self.platform
        return f"{self.name} ({kind}) · {self.id}"


def list_devices(flutter: str) -> list[FlutterDevice]:
    """Supported devices from `flutter devices --machine`."""
    try:
        done = subprocess.run(
            [flutter, "devices", "--machine"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90, creationflags=_NO_WINDOW,
            env=_clean_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise FlutterError(f"flutter devices failed: {e}")
    # Flutter may print notices (e.g. a first-run banner) before the JSON array
    out = done.stdout
    start = out.find("[")
    try:
        data = json.loads(out[start:]) if start >= 0 else []
    except ValueError:
        raise FlutterError(f"flutter devices gave unexpected output:\n{(done.stdout + done.stderr)[-600:]}")
    return [
        FlutterDevice(
            id=d["id"], name=d.get("name", d["id"]), platform=d.get("targetPlatform", ""),
            emulator=bool(d.get("emulator")),
        )
        for d in data if isinstance(d, dict) and d.get("id") and d.get("isSupported", True)
    ]


# --- Service extension toggles (the same ones VS Code and `flutter run` offer) ----------------

@dataclass(frozen=True)
class Toggle:
    label: str
    method: str  # Service extension, e.g. "ext.flutter.debugPaint"
    key: str  # Parameter holding the value
    on: str
    off: str
    modes: tuple = ("debug",)  # Run modes in which the extension exists


_BOOL = {"key": "enabled", "on": "true", "off": "false"}

TOGGLES = [
    Toggle("Debug paint", "ext.flutter.debugPaint", **_BOOL),
    Toggle("Repaint rainbow", "ext.flutter.repaintRainbow", **_BOOL),
    Toggle("Baselines", "ext.flutter.debugPaintBaselinesEnabled", **_BOOL),
    Toggle("Performance overlay", "ext.flutter.showPerformanceOverlay", **_BOOL, modes=("debug", "profile")),
    Toggle("Widget inspector", "ext.flutter.inspector.show", **_BOOL),
    Toggle("Invert oversized images", "ext.flutter.invertOversizedImages", **_BOOL),
    Toggle("Slow animations", "ext.flutter.timeDilation", "timeDilation", "5.0", "1.0"),
    Toggle("Dark mode", "ext.flutter.brightnessOverride", "value", "Brightness.dark", "Brightness.light"),
    Toggle("iOS look", "ext.flutter.platformOverride", "value", "iOS", "android"),
]


# --- The session ------------------------------------------------------------------------------

@dataclass
class Event:
    """Something the window should show: kind is "log", "error", "status", "state" or "exit"."""

    kind: str
    text: str = ""


class FlutterSession:
    """One `flutter run --machine` process. Call poll() from the UI thread to process its output."""

    def __init__(self, flutter: str, settings: FlutterRunSettings):
        self.settings = settings
        self._flutter = flutter
        self._proc: Optional[subprocess.Popen] = None
        self._lines: queue.Queue = queue.Queue()
        self._next_id = 1
        self._pending: dict[int, Callable[[Optional[dict], Optional[str]], None]] = {}
        self._kill_at: Optional[float] = None
        self.app_id: Optional[str] = None
        self.started = False  # app.started seen: the app is running and accepts commands
        self.supports_restart = False
        self.finished = False

    # -- lifecycle --

    def command_line(self) -> list[str]:
        s = self.settings
        args = [self._flutter, "run", "--machine", f"--{s.mode}", "-t", s.target]
        if s.device_id:
            args += ["-d", s.device_id]
        if s.flavor:
            args += ["--flavor", s.flavor]
        args += s.tool_args
        for a in s.app_args:
            args.append(f"--dart-entrypoint-args={a}")
        return args

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self.command_line(), cwd=self.settings.cwd, env=_clean_env(self.settings.env),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=_NO_WINDOW,
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self._proc.stdout:
            self._lines.put(line.rstrip("\r\n"))
        self._lines.put(None)  # EOF: the process ended

    @property
    def running(self) -> bool:
        return self._proc is not None and not self.finished

    def stop(self) -> None:
        """Ask the app to stop; the process tree is killed if it hasn't exited after a grace period."""
        if not self.running or self._kill_at:
            return
        self._kill_at = time.monotonic() + STOP_GRACE_SECONDS
        if self.app_id:
            self._send("app.stop", {"appId": self.app_id})
        else:
            self.kill()  # Never got an app id (still building or failed): nothing to stop gracefully

    def kill(self) -> None:
        """Kill flutter and the Dart/Gradle processes it started."""
        if self._proc and self._proc.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self._proc.pid), "/T", "/F"],
                    capture_output=True, creationflags=_NO_WINDOW,
                )
            else:
                self._proc.kill()

    # -- commands --

    def _send(self, method: str, params: dict, done: Optional[Callable] = None) -> None:
        request_id = self._next_id
        self._next_id += 1
        if done:
            self._pending[request_id] = done
        message = json.dumps([{"id": request_id, "method": method, "params": params}])
        try:
            self._proc.stdin.write(message + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError):
            self._pending.pop(request_id, None)
            if done:
                done(None, "flutter is not running")

    def reload(self, done: Callable[[Optional[str]], None]) -> None:
        """Hot reload. done(error) gets None on success."""
        self._restart(False, done)

    def restart(self, done: Callable[[Optional[str]], None]) -> None:
        """Hot restart. done(error) gets None on success."""
        self._restart(True, done)

    def _restart(self, full: bool, done: Callable[[Optional[str]], None]) -> None:
        if not self.started:
            done("The app is not running yet")
            return

        def finished(result: Optional[dict], error: Optional[str]) -> None:
            if not error and isinstance(result, dict) and result.get("code", 0) != 0:
                error = result.get("message") or "failed"
            done(error)

        self._send("app.restart", {
            "appId": self.app_id, "fullRestart": full, "pause": False, "reason": "manual",
        }, finished)

    def toggle(self, toggle: Toggle, done: Callable[[Optional[bool], Optional[str]], None]) -> None:
        """Flip a service extension. done(is_on, error): reads the current value, then sets the opposite."""
        if not self.started:
            done(None, "The app is not running yet")
            return

        def got_current(result: Optional[dict], error: Optional[str]) -> None:
            if error:
                done(None, error)
                return
            now_on = str((result or {}).get(toggle.key)) == toggle.on
            self.set_extension(toggle, not now_on, done)

        self._call(toggle.method, {}, got_current)

    def set_extension(self, toggle: Toggle, on: bool, done: Callable[[Optional[bool], Optional[str]], None]) -> None:
        value = toggle.on if on else toggle.off

        def finished(result: Optional[dict], error: Optional[str]) -> None:
            if error:
                done(None, error)
            else:
                done(str((result or {}).get(toggle.key, value)) == toggle.on, None)

        self._call(toggle.method, {toggle.key: value}, finished)

    def _call(self, method: str, params: dict, done: Callable) -> None:
        self._send("app.callServiceExtension", {
            "appId": self.app_id, "methodName": method, "params": params,
        }, done)

    # -- output --

    def poll(self) -> list[Event]:
        """Process everything flutter printed since the last call."""
        events: list[Event] = []
        while True:
            try:
                line = self._lines.get_nowait()
            except queue.Empty:
                break
            if line is None:
                self._finish(events)
                break
            self._handle_line(line, events)
        if self._kill_at and not self.finished and time.monotonic() > self._kill_at:
            self.kill()
            self._kill_at = None
        return events

    def _finish(self, events: list[Event]) -> None:
        code = self._proc.wait()
        self.finished = True
        self.started = False
        for done in self._pending.values():
            done(None, "flutter exited")
        self._pending.clear()
        events.append(Event("exit", str(code)))

    def _handle_line(self, line: str, events: list[Event]) -> None:
        text = line.strip()
        if not (text.startswith("[{") and text.endswith("}]")):
            if text:
                events.append(Event("log", line))
            return
        try:
            messages = json.loads(text)
        except ValueError:
            events.append(Event("log", line))
            return
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if "event" in msg:
                self._handle_event(msg["event"], msg.get("params") or {}, events)
            elif "id" in msg:
                done = self._pending.pop(msg["id"], None)
                if done:
                    error = msg.get("error")
                    done(msg.get("result"), None if error is None else str(error))

    def _handle_event(self, name: str, params: dict, events: list[Event]) -> None:
        if name == "app.start":
            self.app_id = params.get("appId")
            self.supports_restart = bool(params.get("supportsRestart"))
            events.append(Event("status", "Building and launching..."))
        elif name == "app.started":
            self.started = True
            events.append(Event("state", "running"))
            events.append(Event("status", "Running"))
        elif name == "app.progress":
            if params.get("finished"):
                events.append(Event("status", "Running" if self.started else ""))
            elif params.get("message"):
                events.append(Event("status", str(params["message"])))
        elif name == "app.log":
            events.append(Event("error" if params.get("error") else "log", str(params.get("log", "")).rstrip()))
        elif name == "daemon.logMessage":
            events.append(Event("error" if params.get("level") == "error" else "log", str(params.get("message", ""))))
        elif name == "app.debugPort":
            events.append(Event("log", f"VM service: {params.get('wsUri') or params.get('baseUri')}"))
        elif name == "app.webLaunchUrl":
            events.append(Event("log", f"Web app: {params.get('url')}"))
        elif name == "app.stop":
            self.started = False
            events.append(Event("status", "Stopping..."))
