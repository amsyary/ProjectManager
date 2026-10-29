"""Message boxes and input prompts dressed in the theme (Enter accepts, Esc cancels)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QVBoxLayout, QWidget,
)

from ui.theme import apply_title_bar


def _box(parent: Optional[QWidget], icon, title: str, text: str) -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    apply_title_bar(box)
    return box


def info(parent: Optional[QWidget], title: str, text: str) -> None:
    _box(parent, QMessageBox.Icon.Information, title, text).exec()


def warn(parent: Optional[QWidget], title: str, text: str) -> None:
    _box(parent, QMessageBox.Icon.Warning, title, text).exec()


def error(parent: Optional[QWidget], title: str, text: str) -> None:
    _box(parent, QMessageBox.Icon.Critical, title, text).exec()


def confirm(parent: Optional[QWidget], title: str, text: str, ok_text: str = "OK", danger: bool = False) -> bool:
    """Ask a yes/no question with a named action. True if the user confirmed."""
    box = _box(parent, QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question, title, text)
    ok = box.addButton(ok_text, QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel if danger else ok)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is ok


def choose(parent: Optional[QWidget], title: str, text: str, options: list[str], default: int = 0) -> Optional[int]:
    """Pick one of several named actions; None when cancelled."""
    box = _box(parent, QMessageBox.Icon.Question, title, text)
    buttons = [box.addButton(o, QMessageBox.ButtonRole.AcceptRole) for o in options]
    cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(buttons[default])
    box.setEscapeButton(cancel)
    box.exec()
    clicked = box.clickedButton()
    return buttons.index(clicked) if clicked in buttons else None


class _PromptDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], title: str, label: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(10)
        text = QLabel(label)
        text.setWordWrap(True)
        self._layout.addWidget(text)

    def add_buttons(self, ok_text: str) -> None:
        from ui.widgets import ToolSlot

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        cancel = ToolSlot("Cancel")
        cancel.clicked.connect(self.reject)
        ok = ToolSlot(ok_text, variant="primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        self._layout.addSpacing(6)
        self._layout.addLayout(row)

    def showEvent(self, event) -> None:
        apply_title_bar(self)
        super().showEvent(event)


def ask_text(
    parent: Optional[QWidget], title: str, label: str, initial: str = "",
    password: bool = False, ok_text: str = "OK", mono: bool = False,
) -> Optional[str]:
    """One-line text prompt. None if cancelled."""
    dlg = _PromptDialog(parent, title, label)
    field = QLineEdit(initial)
    if mono:
        field.setProperty("mono", True)
    if password:
        field.setEchoMode(QLineEdit.EchoMode.Password)
    field.returnPressed.connect(dlg.accept)
    dlg._layout.addWidget(field)
    dlg.add_buttons(ok_text)
    field.selectAll()
    field.setFocus()
    return field.text() if dlg.exec() == QDialog.DialogCode.Accepted else None


def ask_pick(
    parent: Optional[QWidget], title: str, label: str, labels: list[str], values: list[str],
    default: Optional[str] = None, ok_text: str = "Run",
) -> Optional[str]:
    """Pick one value from a list (double-click or Enter accepts). None if cancelled."""
    dlg = _PromptDialog(parent, title, label)
    lst = QListWidget()
    lst.setObjectName("Plain")
    lst.addItems(labels)
    lst.setMinimumHeight(min(max(len(labels), 3), 12) * 34)
    start = values.index(str(default)) if default is not None and str(default) in values else 0
    if labels:
        lst.setCurrentRow(start)
    lst.itemDoubleClicked.connect(lambda _: dlg.accept())
    lst.itemActivated.connect(lambda _: dlg.accept())
    dlg._layout.addWidget(lst)
    hint = QLabel("Double-click or press Enter to choose.")
    hint.setProperty("role", "dim")
    dlg._layout.addWidget(hint)
    dlg.add_buttons(ok_text)
    lst.setFocus()
    if dlg.exec() != QDialog.DialogCode.Accepted or lst.currentRow() < 0:
        return None
    return values[lst.currentRow()]
