"""Dialog for editing a sub-project's terminal commands (e.g. npm run dev, npm run build)."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

from models.project import SubProjectCommand
from ui import dialogs
from ui.theme import apply_title_bar
from ui.widgets import FoamPanel, ToolSlot


class _CommandRow(FoamPanel):
    def __init__(self, on_remove, name: str = "", command: str = "", run_on_open: bool = False):
        super().__init__(radius=10)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 14)
        layout.setSpacing(8)
        self.name = QLineEdit(name)
        self.name.setPlaceholderText("Name (optional)")
        self.name.setFixedWidth(170)
        self.command = QLineEdit(command)
        self.command.setPlaceholderText("npm run dev")
        self.command.setProperty("mono", True)
        self.run_on_open = QCheckBox("Run when opened")
        self.run_on_open.setChecked(run_on_open)
        self.run_on_open.setToolTip("Also start this command when the folder is opened (Open / Open all)")
        remove = ToolSlot("", "trash", variant="danger", tooltip="Remove this command")
        remove.clicked.connect(lambda: on_remove(self))
        layout.addWidget(self.name)
        layout.addWidget(self.command, 1)
        layout.addWidget(self.run_on_open)
        layout.addWidget(remove)


class CommandsDialog(QDialog):
    """Modal list editor: each command has a name, the command line, and a Run-when-opened flag."""

    def __init__(self, parent: Optional[QWidget], commands: list[SubProjectCommand], title: str = "Commands"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 420)
        self.setMinimumSize(560, 300)
        self._rows: list[_CommandRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        intro = QLabel("Commands run in a terminal inside the folder. Name them to keep the Run menu short.")
        intro.setProperty("role", "dim")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self._list = QVBoxLayout()
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(6)
        self._list.addStretch()
        holder = QWidget()
        holder.setLayout(self._list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(scroll, 1)

        add = ToolSlot("Add command", "plus")
        add.clicked.connect(lambda: self._add_row(focus=True))
        root.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = ToolSlot("Cancel")
        cancel.clicked.connect(self.reject)
        save = ToolSlot("Save commands", "check", variant="primary")
        save.setDefault(True)  # Enter in any field saves
        save.clicked.connect(self._on_save)
        footer.addWidget(cancel)
        footer.addWidget(save)
        root.addLayout(footer)

        for c in commands:
            self._add_row(c.name or "", c.command, c.run_on_open)
        if not commands:
            self._add_row(focus=True)
        self.result_commands: Optional[list[SubProjectCommand]] = None

    def showEvent(self, event) -> None:
        apply_title_bar(self)
        super().showEvent(event)

    def _add_row(self, name: str = "", command: str = "", run_on_open: bool = False, focus: bool = False) -> None:
        row = _CommandRow(self._remove_row, name, command, run_on_open)
        self._list.insertWidget(self._list.count() - 1, row)
        self._rows.append(row)
        if focus:
            row.command.setFocus()

    def _remove_row(self, row: _CommandRow) -> None:
        self._rows.remove(row)
        row.deleteLater()

    def _on_save(self) -> None:
        commands = []
        for row in self._rows:
            command = row.command.text().strip()
            name = row.name.text().strip() or None
            if not command:
                if name:
                    dialogs.error(self, "Missing command", f'"{name}" has no command.')
                    row.command.setFocus()
                    return
                continue
            commands.append(SubProjectCommand(command=command, name=name, run_on_open=row.run_on_open.isChecked()))
        self.result_commands = commands
        self.accept()

    @classmethod
    def edit(cls, parent: Optional[QWidget], commands: list[SubProjectCommand], title: str) -> Optional[list[SubProjectCommand]]:
        """Show the dialog; the new list on Save, None on Cancel."""
        dlg = cls(parent, commands, title)
        return dlg.result_commands if dlg.exec() == QDialog.DialogCode.Accepted else None
