"""Side panel of saved text snippets: copy with one click, add, edit, delete."""

from __future__ import annotations

import uuid
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget,
)

from models.project import TextSnippet
from services.project_service import ProjectService
from ui import dialogs
from ui.theme import SIZE_META, apply_title_bar, label_font, mono_font
from ui.widgets import FoamPanel, ToolSlot

PREVIEW_LINES = 6


def _preview(text: str) -> str:
    lines = text.splitlines() or [""]
    shown = [line if len(line) <= 120 else line[:119] + "…" for line in lines[:PREVIEW_LINES]]
    if len(lines) > PREVIEW_LINES:
        shown.append(f"… {len(lines) - PREVIEW_LINES} more lines")
    return "\n".join(shown)


class _SnippetCard(FoamPanel):
    def __init__(self, panel: "TextPanel", snippet: TextSnippet):
        super().__init__(radius=10)
        self.snippet = snippet
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 10, 14)
        layout.setSpacing(8)
        text = QLabel(_preview(snippet.content))
        text.setFont(mono_font(SIZE_META))
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.setToolTip(snippet.content[:1500])
        layout.addWidget(text)

        bar = QHBoxLayout()
        bar.setSpacing(2)
        self.copy = ToolSlot("Copy", "copy", compact=True)
        self.copy.clicked.connect(self._copy)
        edit = ToolSlot("", "edit", compact=True, variant="quiet", tooltip="Edit snippet")
        edit.clicked.connect(lambda: panel.edit_snippet(snippet))
        delete = ToolSlot("", "trash", compact=True, variant="danger", tooltip="Delete snippet")
        delete.clicked.connect(lambda: panel.delete_snippet(snippet))
        bar.addWidget(self.copy)
        bar.addStretch()
        bar.addWidget(edit)
        bar.addWidget(delete)
        layout.addLayout(bar)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.snippet.content)
        self.copy.setText("Copied")
        self.copy.set_icon_name("check")
        self.copy.set_active(True)
        QTimer.singleShot(1300, self._reset_copy)

    def _reset_copy(self) -> None:
        try:
            self.copy.setText("Copy")
            self.copy.set_icon_name("copy")
            self.copy.set_active(False)
        except RuntimeError:
            pass  # Card was rebuilt meanwhile


class TextPanel(QWidget):
    """Right-side panel for text snippet management."""

    def __init__(self, service: ProjectService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = service
        self.setObjectName("Rail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(260)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 10, 10)
        root.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel("Snippets")
        title.setFont(label_font(semibold=True))
        head.addWidget(title)
        self._count = QLabel("")
        self._count.setProperty("role", "dim")
        head.addWidget(self._count)
        head.addStretch()
        add = ToolSlot("Add", "plus", compact=True, tooltip="Add a text snippet")
        add.clicked.connect(lambda: self.edit_snippet(None))
        head.addWidget(add)
        root.addLayout(head)

        self._list = QVBoxLayout()
        self._list.setContentsMargins(0, 0, 4, 0)
        self._list.setSpacing(4)
        holder = QWidget()
        holder.setLayout(self._list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)
        self.refresh()

    def refresh(self) -> None:
        while self._list.count():
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        snippets = self._service.get_snippets()
        self._count.setText(str(len(snippets)) if snippets else "")
        if not snippets:
            empty = QLabel("No snippets yet.\nKeep keys, commands or text you paste often here.")
            empty.setProperty("role", "dim")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list.addSpacing(24)
            self._list.addWidget(empty)
        for snippet in snippets:
            self._list.addWidget(_SnippetCard(self, snippet))
        self._list.addStretch()

    def delete_snippet(self, snippet: TextSnippet) -> None:
        if dialogs.confirm(self.window(), "Delete snippet", "Delete this text snippet?", "Delete", danger=True):
            self._service.delete_snippet(snippet.id)
            self.refresh()

    def edit_snippet(self, snippet: Optional[TextSnippet]) -> None:
        dlg = QDialog(self.window())
        dlg.setWindowTitle("Add snippet" if snippet is None else "Edit snippet")
        dlg.resize(560, 360)
        dlg.setMinimumSize(360, 220)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)
        editor = QPlainTextEdit(snippet.content if snippet else "")
        editor.setProperty("mono", True)
        editor.setPlaceholderText("Text to keep at hand")
        root.addWidget(editor, 1)
        footer = QHBoxLayout()
        hint = QLabel("Ctrl+S saves")
        hint.setProperty("role", "dim")
        footer.addWidget(hint)
        footer.addStretch()
        cancel = ToolSlot("Cancel")
        cancel.clicked.connect(dlg.reject)
        save = ToolSlot("Save snippet", "check", variant="primary")
        footer.addWidget(cancel)
        footer.addWidget(save)
        root.addLayout(footer)

        def on_save():
            content = editor.toPlainText()
            if not content.strip():
                dialogs.warn(dlg, "Empty snippet", "Type some text to save.")
                return
            if snippet is None:
                self._service.add_snippet(TextSnippet(id=str(uuid.uuid4()), content=content))
            else:
                snippet.content = content
                self._service.update_snippet(snippet)
            dlg.accept()
            self.refresh()

        save.clicked.connect(on_save)
        QShortcut(QKeySequence("Ctrl+S"), dlg, on_save)
        editor.setFocus()
        apply_title_bar(dlg)
        dlg.exec()
