"""Top-bar tool that mirrors an Android device (or all of them) with scrcpy."""

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from services.scrcpy_launcher import ScrcpyLauncher, ScrcpyError, AdbDevice, SCRCPY_START_FAILED
from ui import dialogs
from ui.widgets import Menu, ToolSlot

POLL_MS = 1000


class ScrcpyButton(ToolSlot):
    """Click to pick a device from `adb devices`; scrcpy runs without a console window.

    While mirroring, the slot shows its yellow floor: the tool is out.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("scrcpy", "phone", parent, arrow=True, compact=True,
                         tooltip="Mirror an Android device with scrcpy")
        self._launcher = ScrcpyLauncher()
        self._timer = QTimer(self, interval=POLL_MS)
        self._timer.timeout.connect(self._poll)
        self.clicked.connect(self._show_menu)

    def _show_menu(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            devices = self._launcher.list_devices()
        except ScrcpyError as e:
            QApplication.restoreOverrideCursor()
            dialogs.error(self.window(), "scrcpy", str(e))
            return
        QApplication.restoreOverrideCursor()

        menu = Menu(self)
        ready = [d for d in devices if d.is_ready]
        for d in devices:
            label = d.display_name()
            if label != d.serial:
                label += f"   ({d.serial})"
            if not d.is_ready:
                menu.add(f"{label}  ·  {d.state}", enabled=False, icon_name="phone")
            elif self._launcher.is_running(d.serial):
                menu.add(f"{label}  ·  mirroring", enabled=False, icon_name="phone")
            else:
                menu.add(label, lambda _=False, d=d: self._start([d]), icon_name="phone")

        if not devices:
            menu.add("No devices found. Connect a phone with USB debugging enabled.", enabled=False)
        if any(not d.is_ready for d in devices):
            menu.add("Unauthorized or offline: accept the USB debugging prompt on the phone", enabled=False)

        not_running = [d for d in ready if not self._launcher.is_running(d.serial)]
        if len(ready) > 1:
            menu.addSeparator()
            menu.add(f"Run on all ({len(not_running)})", lambda: self._start(not_running), enabled=bool(not_running))
        menu.popup_below(self)

    def _start(self, devices: list[AdbDevice]) -> None:
        for d in devices:
            try:
                self._launcher.start(d)
            except ScrcpyError as e:
                dialogs.error(self.window(), "scrcpy", str(e))
                break
        self._show_count()
        if self._launcher.has_sessions() and not self._timer.isActive():
            self._timer.start()

    def _show_count(self) -> None:
        n = self._launcher.session_count()
        self.set_out(n > 0)
        self.setText(f"Mirroring · {n}" if n else "scrcpy")

    def _poll(self) -> None:
        """Forget closed sessions and report ones that failed to start."""
        for session in self._launcher.pop_finished():
            if session.process.returncode == SCRCPY_START_FAILED:
                dialogs.error(
                    self.window(), "scrcpy",
                    f"scrcpy failed on {session.device.display_name()}:\n\n{session.log_tail()}",
                )
        self._show_count()
        if not self._launcher.has_sessions():
            self._timer.stop()
