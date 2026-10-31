"""Side panel with the log of any Flutter run, a switcher between runs and a few small controls."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import dialogs
from ui.log_view import LogView
from ui.run_manager import Run, RunManager
from ui.theme import label_font
from ui.widgets import Combo, StatusLamp, ToolSlot

STATUS_MS = 250

_STATE_WORD = {"building": "building", "running": "running", "stopping": "stopping"}


def _state_word(run: Run) -> str:
    state = run.state()
    if state:
        return _STATE_WORD[state]
    return "failed" if run.failed else "stopped"


class LogPanel(QWidget):
    """Right-side panel: pick a run, read its colored log, reload/restart/stop it."""

    close_requested = Signal()
    open_window = Signal(str)  # Run id: show the Flutter window of its folder

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = RunManager.get()
        self._selected: Optional[str] = None
        self._ids: list[str] = []
        self.setObjectName("Rail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(340)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 10, 10)
        root.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel("Logs")
        title.setFont(label_font(semibold=True))
        head.addWidget(title)
        self._count = QLabel("")
        self._count.setProperty("role", "dim")
        head.addWidget(self._count)
        head.addStretch()
        close = ToolSlot("", "close", compact=True, variant="quiet", tooltip="Hide the logs")
        close.clicked.connect(self.close_requested)
        head.addWidget(close)
        root.addLayout(head)

        self._picker = Combo()
        self._picker.setToolTip("Switch to another run's log")
        self._picker.activated.connect(lambda i: self.show_run(self._picker.itemData(i)))
        root.addWidget(self._picker)

        status = QHBoxLayout()
        status.setSpacing(8)
        self._lamp = StatusLamp()
        status.addWidget(self._lamp)
        self._status = QLabel("")
        self._status.setProperty("role", "dim")
        status.addWidget(self._status, 1)
        root.addLayout(status)

        tools = QHBoxLayout()
        tools.setSpacing(2)
        self._reload = ToolSlot("", "bolt", compact=True, tooltip="Hot reload")
        self._reload.clicked.connect(lambda: self._act(lambda rid: self._manager.reload(rid, False)))
        self._restart = ToolSlot("", "restart", compact=True, tooltip="Hot restart")
        self._restart.clicked.connect(lambda: self._act(lambda rid: self._manager.reload(rid, True)))
        self._stop = ToolSlot("", "stop", compact=True, variant="danger", tooltip="Stop")
        self._stop.clicked.connect(self._stop_or_run)
        self._window = ToolSlot("", "external", compact=True, variant="quiet", tooltip="Open the Flutter window")
        self._window.clicked.connect(lambda: self._act(self.open_window.emit))
        self._tag = ToolSlot("", "tag", compact=True, variant="quiet", tooltip="Name this device")
        self._tag.clicked.connect(self._rename)
        for w in (self._reload, self._restart, self._stop):
            tools.addWidget(w)
        tools.addSpacing(8)
        tools.addWidget(self._window)
        tools.addWidget(self._tag)
        tools.addStretch()
        self._clear = ToolSlot("Clear", "erase", compact=True, variant="quiet", tooltip="Clear this log")
        self._clear.clicked.connect(lambda: self._act(self._manager.clear_log))
        self._dismiss = ToolSlot("", "close", compact=True, variant="quiet", tooltip="Remove this stopped run and its log")
        self._dismiss.clicked.connect(lambda: self._act(self._manager.dismiss))
        tools.addWidget(self._clear)
        tools.addWidget(self._dismiss)
        self._tools = QWidget()
        self._tools.setLayout(tools)
        tools.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._tools)

        self._log = LogView()
        root.addWidget(self._log, 1)
        self._empty = QLabel("Nothing has run yet.\nStart a Flutter app and its log shows here.")
        self._empty.setProperty("role", "dim")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._empty, 1)

        self._timer = QTimer(self, interval=STATUS_MS)
        self._timer.timeout.connect(self._refresh_status)
        self._manager.changed.connect(self._sync)
        self._manager.logged.connect(self._on_logged)
        self._manager.log_cleared.connect(self._on_cleared)
        self._sync()

    # -- public --

    def show_run(self, rid: Optional[str]) -> None:
        if rid == self._selected:
            return
        self._selected = rid
        run = self._manager.run(rid)
        self._log.set_lines(run.log if run else [])
        self._sync()

    def show_folder(self, folder: str) -> None:
        """Show a run of folder: a running one first."""
        runs = self._manager.runs(folder)
        current = self._manager.run(self._selected)
        if current in runs:
            return
        pick = next((r for r in runs if r.active), runs[0] if runs else None)
        if pick:
            self.show_run(pick.id)

    # -- events --

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()
        self._sync()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _act(self, action) -> None:
        if self._selected and self._manager.run(self._selected):
            action(self._selected)

    def _stop_or_run(self) -> None:
        run = self._manager.run(self._selected)
        if run is None:
            return
        if run.active:
            self._manager.stop(run.id)
        else:
            error = self._manager.run_again(run.id)
            if error:
                dialogs.error(self.window(), "Flutter", error)

    def _rename(self) -> None:
        from ui.flutter_run_window import rename_device

        run = self._manager.run(self._selected)
        if run:
            rename_device(self.window(), run.device_id, run.model)

    def _on_logged(self, rid: str, lines) -> None:
        if rid == self._selected:
            self._log.append_lines(lines)

    def _on_cleared(self, rid: str) -> None:
        if rid == self._selected:
            self._log.clear()

    # -- state --

    def _sync(self) -> None:
        runs = self._manager.runs()
        ids = [r.id for r in runs]
        if self._selected not in ids:
            pick = next((r.id for r in runs if r.active), ids[0] if ids else None)
            if pick != self._selected:
                self.show_run(pick)
                return
        if ids != self._ids:
            self._ids = ids
            self._picker.clear()
            for run in runs:
                self._picker.addItem(run.title, run.id)
        for i, run in enumerate(runs):
            text = f"{run.title}  ·  {_state_word(run)}"
            if self._picker.itemText(i) != text:
                self._picker.setItemText(i, text)
        if self._selected in ids:
            self._picker.setCurrentIndex(ids.index(self._selected))
        active = sum(1 for r in runs if r.active)
        self._count.setText(f"{active} running" if active else "")

        has = bool(runs)
        for w in (self._picker, self._tools, self._log):
            w.setVisible(has)
        self._empty.setVisible(not has)
        self._lamp.setVisible(has)
        self._status.setVisible(has)

        run = self._manager.run(self._selected)
        self._reload.setEnabled(bool(run and run.reloadable))
        self._restart.setEnabled(bool(run and run.reloadable))
        if run and run.active:
            self._stop.set_icon_name("stop")
            self._stop.set_variant("danger")
            self._stop.setToolTip("Stop")
            self._stop.setEnabled(not run.stopping)
        else:
            self._stop.set_icon_name("play")
            self._stop.set_variant("normal")
            self._stop.setToolTip("Run again with the same settings")
            self._stop.setEnabled(bool(run and run.settings))
        self._dismiss.setVisible(bool(run and not run.active))
        self._refresh_status()

    def _refresh_status(self) -> None:
        run = self._manager.run(self._selected)
        if run is None:
            return
        state = run.state()
        text = run.status_text()
        if self._status.text() != text:
            self._status.setText(text)
        self._lamp.set_state(
            "busy" if state in ("building", "stopping") else "running" if state == "running"
            else "error" if run.failed else "idle"
        )
