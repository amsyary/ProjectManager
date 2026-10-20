"""Top-bar button that mirrors an Android device (or all of them) with scrcpy."""

import tkinter as tk
from tkinter import ttk, messagebox

from services.scrcpy_launcher import ScrcpyLauncher, ScrcpyError, AdbDevice, SCRCPY_START_FAILED

POLL_MS = 1000


class ScrcpyButton(ttk.Button):
    """Click to pick a device from `adb devices`; scrcpy runs without a console window."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="scrcpy ▾", command=self._show_menu, **kwargs)
        self._launcher = ScrcpyLauncher()
        self._polling = False

    def _show_menu(self) -> None:
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            devices = self._launcher.list_devices()
        except ScrcpyError as e:
            messagebox.showerror("scrcpy", str(e))
            return
        finally:
            self.configure(cursor="")

        menu = tk.Menu(self, tearoff=0)
        ready = [d for d in devices if d.is_ready]
        for d in devices:
            label = d.display_name()
            if label != d.serial:
                label += f"   ({d.serial})"
            if not d.is_ready:
                menu.add_command(label=f"{label} - {d.state}", state="disabled")
            elif self._launcher.is_running(d.serial):
                menu.add_command(label=f"{label} - running", state="disabled")
            else:
                menu.add_command(label=label, command=lambda d=d: self._start([d]))

        if not devices:
            menu.add_command(
                label="No devices found. Connect a phone with USB debugging enabled.",
                state="disabled",
            )
        if any(not d.is_ready for d in devices):
            menu.add_command(
                label="Unauthorized/offline: accept the USB debugging prompt on the phone",
                state="disabled",
            )

        not_running = [d for d in ready if not self._launcher.is_running(d.serial)]
        if len(ready) > 1:
            menu.add_separator()
            menu.add_command(
                label=f"Run on all ({len(not_running)})",
                command=lambda: self._start(not_running),
                state="normal" if not_running else "disabled",
            )
        menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())

    def _start(self, devices: list[AdbDevice]) -> None:
        for d in devices:
            try:
                self._launcher.start(d)
            except ScrcpyError as e:
                messagebox.showerror("scrcpy", str(e))
                return
        if not self._polling:
            self._polling = True
            self.after(POLL_MS, self._poll)

    def _poll(self) -> None:
        """Forget closed sessions and report ones that failed to start."""
        for session in self._launcher.pop_finished():
            if session.process.returncode == SCRCPY_START_FAILED:
                messagebox.showerror(
                    "scrcpy",
                    f"scrcpy failed on {session.device.display_name()}:\n\n{session.log_tail()}",
                )
        if self._launcher.has_sessions():
            self.after(POLL_MS, self._poll)
        else:
            self._polling = False
