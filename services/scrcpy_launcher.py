"""List adb devices and mirror them with scrcpy, without showing a console window."""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Hide console windows for adb/scrcpy (both are console programs)
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# scrcpy exit codes: 0 = window closed, 1 = failed to start, 2 = device disconnected
SCRCPY_START_FAILED = 1


class ScrcpyError(Exception):
    """scrcpy/adb is missing or adb could not list devices."""


@dataclass
class AdbDevice:
    """A device line from `adb devices -l`."""

    serial: str
    state: str  # "device" when ready; also "unauthorized", "offline", ...
    model: Optional[str] = None

    @property
    def is_ready(self) -> bool:
        return self.state == "device"

    def display_name(self) -> str:
        """Model name if adb reports one (underscores as spaces), else the serial."""
        return self.model.replace("_", " ") if self.model else self.serial


@dataclass
class ScrcpySession:
    """A running scrcpy process for one device."""

    device: AdbDevice
    process: subprocess.Popen
    log_path: Path

    def log_tail(self, lines: int = 15) -> str:
        """Last lines of scrcpy's output, for error messages."""
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(text.strip().splitlines()[-lines:])


def find_adb() -> Optional[str]:
    """First adb on PATH, the same one used for listing and for scrcpy."""
    return shutil.which("adb")


def find_scrcpy() -> Optional[str]:
    return shutil.which("scrcpy")


class ScrcpyLauncher:
    """Lists devices and keeps track of one scrcpy session per device."""

    def __init__(self):
        self._sessions: dict[str, ScrcpySession] = {}  # serial -> session

    def list_devices(self) -> list[AdbDevice]:
        """Return devices from `adb devices -l`. Raises ScrcpyError if adb is unavailable."""
        adb = find_adb()
        if not adb:
            raise ScrcpyError("adb was not found on PATH.")
        try:
            subprocess.run(
                [adb, "start-server"], capture_output=True, timeout=15, creationflags=_NO_WINDOW
            )
            result = subprocess.run(
                [adb, "devices", "-l"],
                capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ScrcpyError(f"Could not run adb: {e}") from e

        devices = []
        for line in result.stdout.splitlines()[1:]:  # skip "List of devices attached"
            parts = line.split()
            if len(parts) < 2:
                continue
            model = next((p[len("model:"):] for p in parts[2:] if p.startswith("model:")), None)
            devices.append(AdbDevice(serial=parts[0], state=parts[1], model=model))
        return devices

    def is_running(self, serial: str) -> bool:
        session = self._sessions.get(serial)
        return session is not None and session.process.poll() is None

    def start(self, device: AdbDevice) -> None:
        """Start scrcpy for device in the background. Raises ScrcpyError if scrcpy is missing."""
        scrcpy = find_scrcpy()
        if not scrcpy:
            raise ScrcpyError("scrcpy was not found on PATH.")
        if self.is_running(device.serial):
            return

        env = dict(os.environ)
        adb = find_adb()
        if adb:
            env["ADB"] = adb  # same adb as list_devices, so two adb versions don't fight
        safe_serial = re.sub(r"[^\w.-]", "_", device.serial)
        log_path = Path(tempfile.gettempdir()) / f"projectmanager-scrcpy-{safe_serial}.log"
        try:
            with open(log_path, "w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [scrcpy, "-s", device.serial, "--window-title", device.display_name()],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    env=env, creationflags=_NO_WINDOW,
                )
        except OSError as e:
            raise ScrcpyError(f"Could not start scrcpy: {e}") from e
        self._sessions[device.serial] = ScrcpySession(device, process, log_path)

    def has_sessions(self) -> bool:
        return bool(self._sessions)

    def pop_finished(self) -> list[ScrcpySession]:
        """Remove and return sessions whose scrcpy window has closed (or device disconnected)."""
        finished = [s for s in self._sessions.values() if s.process.poll() is not None]
        for s in finished:
            del self._sessions[s.device.serial]
        return finished
