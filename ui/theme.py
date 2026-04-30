"""Light / dark theme management for the application."""

import tkinter as tk
from tkinter import ttk

DARK: dict = {
    "bg": "#1e1e1e",
    "bg_card": "#1e1e1e",
    "bg_input": "#3c3c3c",
    "fg": "#d4d4d4",
    "fg_dim": "#888888",
    "border": "#474747",
    "select_bg": "#0078d4",
    "select_fg": "#ffffff",
    "tooltip_bg": "#252526",
    "tooltip_fg": "#cccccc",
}

LIGHT: dict = {
    "bg": "SystemButtonFace",
    "bg_card": "SystemButtonFace",
    "bg_input": "SystemWindow",
    "fg": "SystemWindowText",
    "fg_dim": "gray",
    "border": "SystemButtonShadow",
    "select_bg": "#0078d4",
    "select_fg": "#ffffff",
    "tooltip_bg": "#ffffe0",
    "tooltip_fg": "#000000",
}


class ThemeManager:
    """Singleton that manages light / dark theme via ttk.Style."""

    _instance: "ThemeManager | None" = None

    def __new__(cls) -> "ThemeManager":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._dark = False
            inst._style: ttk.Style | None = None
            inst._default_theme = "default"
            cls._instance = inst
        return cls._instance

    @property
    def is_dark(self) -> bool:
        return self._dark

    @property
    def colors(self) -> dict:
        return DARK if self._dark else LIGHT

    def init(self, root: tk.Tk, dark: bool = False) -> None:
        self._style = ttk.Style(root)
        try:
            self._default_theme = self._style.theme_use()
        except Exception:
            self._default_theme = "default"
        self._dark = dark
        self._apply_style()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._apply_style()

    def toggle(self) -> bool:
        self.set_dark(not self._dark)
        return self._dark

    def _apply_style(self) -> None:
        if not self._style:
            return
        c = self.colors
        if self._dark:
            self._style.theme_use("clam")
            self._style.configure(".",
                background=c["bg"],
                foreground=c["fg"],
                fieldbackground=c["bg_input"],
                troughcolor=c["bg"],
                bordercolor=c["border"],
                darkcolor=c["bg"],
                lightcolor=c["bg"],
                selectbackground=c["select_bg"],
                selectforeground=c["select_fg"],
                insertcolor=c["fg"],
            )
            self._style.configure("TFrame", background=c["bg"])
            self._style.configure("TLabel", background=c["bg"], foreground=c["fg"])
            self._style.configure("TButton",
                background=c["bg_input"],
                foreground=c["fg"],
                bordercolor=c["border"],
                focuscolor=c["bg"],
                padding=4,
            )
            self._style.map("TButton",
                background=[("active", "#4a4a4a"), ("pressed", "#555555")],
                foreground=[("active", c["fg"]), ("pressed", c["fg"])],
            )
            self._style.configure("TEntry",
                fieldbackground=c["bg_input"],
                foreground=c["fg"],
                insertcolor=c["fg"],
                bordercolor=c["border"],
            )
            self._style.configure("TCombobox",
                fieldbackground=c["bg_input"],
                foreground=c["fg"],
                arrowcolor=c["fg"],
                bordercolor=c["border"],
            )
            self._style.map("TCombobox",
                fieldbackground=[("readonly", c["bg_input"])],
                foreground=[("readonly", c["fg"])],
                selectbackground=[("readonly", c["select_bg"])],
                selectforeground=[("readonly", c["select_fg"])],
            )
            self._style.configure("TScrollbar",
                background=c["bg_input"],
                troughcolor=c["bg"],
                arrowcolor=c["fg"],
                bordercolor=c["border"],
                relief="flat",
            )
            self._style.map("TScrollbar",
                background=[("active", "#555555")],
            )
            self._style.configure("TSeparator", background=c["border"])
            self._style.configure("TPanedwindow", background=c["bg"])
        else:
            self._style.theme_use(self._default_theme)
