"""Project card widget for the grid view."""

import tkinter as tk
from tkinter import ttk

from models.project import Project
from ui.icon_loader import load_icon
from services.project_service import ProjectService
from ui.theme import ThemeManager


class ProjectCard(tk.Frame):
    """A card displaying a project (icon + name). Click to select, right-click for menu."""

    CARD_SIZE = 120

    def __init__(
        self,
        parent,
        project: Project,
        on_click=None,
        on_edit=None,
        on_delete=None,
        is_selected=False,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.project = project
        self.on_click = on_click
        self.on_edit = on_edit
        self.on_delete = on_delete
        self._icons_dir = ProjectService.icons_dir()
        self._build_ui()
        self.set_selected(is_selected)

    def _build_ui(self):
        self.configure(padx=8, pady=8, bg=ThemeManager().colors["bg_card"])
        self.bind("<Button-1>", self._on_left_click)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Button-3>", self._on_right_click)

        inner = ttk.Frame(self)
        inner.pack(fill="both", expand=True)
        inner.bind("<Button-1>", self._on_left_click)
        inner.bind("<Double-Button-1>", self._on_double_click)
        inner.bind("<Button-3>", self._on_right_click)

        icon_path = self.project.icon_path
        if icon_path:
            photo = load_icon(icon_path, (64, 64))
            if photo:
                self._icon_label = ttk.Label(inner, image=photo)
                self._icon_label.image = photo
                self._icon_label.pack(pady=(0, 4))
                self._icon_label.bind("<Button-1>", self._on_left_click)
                self._icon_label.bind("<Double-Button-1>", self._on_double_click)
                self._icon_label.bind("<Button-3>", self._on_right_click)
            else:
                self._icon_label = None
        else:
            self._icon_label = None

        self._name_label = ttk.Label(
            inner, text=self.project.name, wraplength=self.CARD_SIZE - 16
        )
        self._name_label.pack()
        self._name_label.bind("<Button-1>", self._on_left_click)
        self._name_label.bind("<Double-Button-1>", self._on_double_click)
        self._name_label.bind("<Button-3>", self._on_right_click)

    def _on_left_click(self, event):
        if self.on_click:
            self.on_click(self.project)

    def _on_double_click(self, event):
        if self.on_edit:
            self.on_edit(self.project)

    def _on_right_click(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edit", command=lambda: self.on_edit and self.on_edit(self.project))
        menu.add_command(
            label="Delete",
            command=lambda: self.on_delete and self.on_delete(self.project),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def set_selected(self, selected: bool) -> None:
        """Update the card's selected state (border indicator)."""
        if selected:
            self.configure(
                highlightbackground="#0078d4",
                highlightcolor="#0078d4",
                highlightthickness=2,
                bd=0,
            )
        else:
            self.configure(highlightthickness=0, bd=0)
