"""Popup for editing a sub-project's terminal commands (e.g. npm run dev, npm run build)."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from models.project import SubProjectCommand
from ui.theme import ThemeManager


class CommandsDialog(tk.Toplevel):
    """Modal list editor: each command has a name, the command line, and a Run-when-opened flag."""

    def __init__(
        self,
        parent,
        commands: list[SubProjectCommand],
        title: str = "Commands",
        on_save: Callable[[list[SubProjectCommand]], None] | None = None,
    ):
        super().__init__(parent)
        self.on_save = on_save
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=ThemeManager().colors["bg"])

        # (row, name_var, command_var, run_on_open_var)
        self._rows: list[tuple[ttk.Frame, tk.StringVar, tk.StringVar, tk.BooleanVar]] = []
        self._build_ui()
        for c in commands:
            self._add_row(c.name or "", c.command, c.run_on_open)
        if not commands:
            self._add_row()

        self._center_on_parent(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Commands run in a terminal inside the sub-project folder.",
        ).pack(anchor="w", pady=(0, 6))

        header = ttk.Frame(main)
        header.pack(fill="x")
        ttk.Label(header, text="Name (optional)", width=20).pack(side="left", padx=(0, 4))
        ttk.Label(header, text="Command").pack(side="left", padx=4)

        self._rows_frame = ttk.Frame(main)
        self._rows_frame.pack(fill="both", expand=True, pady=4)

        ttk.Button(main, text="+ Add command", command=self._add_row).pack(anchor="w", pady=(4, 0))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=(12, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="left", padx=4)

    def _add_row(self, name: str = "", command: str = "", run_on_open: bool = False):
        row = ttk.Frame(self._rows_frame)
        row.pack(fill="x", pady=2)

        name_var = tk.StringVar(value=name)
        command_var = tk.StringVar(value=command)
        run_on_open_var = tk.BooleanVar(value=run_on_open)

        ttk.Entry(row, textvariable=name_var, width=20).pack(side="left", padx=(0, 4))
        command_entry = ttk.Entry(row, textvariable=command_var, width=40)
        command_entry.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Checkbutton(row, text="Run when opened", variable=run_on_open_var).pack(
            side="left", padx=4
        )

        def remove():
            row.destroy()
            self._rows[:] = [r for r in self._rows if r[0] != row]

        ttk.Button(row, text="Remove", command=remove).pack(side="left", padx=4)

        self._rows.append((row, name_var, command_var, run_on_open_var))
        command_entry.focus_set()

    def _center_on_parent(self, parent: tk.Tk | tk.Toplevel) -> None:
        """Position this dialog centered over the parent window."""
        self.update_idletasks()
        dw = max(self.winfo_reqwidth(), 640)
        dh = self.winfo_reqheight() + 120  # room for a few more rows
        x = parent.winfo_rootx() + (parent.winfo_width() - dw) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - dh) // 2
        self.geometry(f"{dw}x{dh}+{max(0, x)}+{max(0, y)}")

    def _on_save(self):
        commands = []
        for _, name_var, command_var, run_on_open_var in self._rows:
            command = command_var.get().strip()
            name = name_var.get().strip() or None
            if not command:
                if name:
                    messagebox.showerror(
                        "Missing command", f'"{name}" has no command.', parent=self
                    )
                    return
                continue
            commands.append(
                SubProjectCommand(command=command, name=name, run_on_open=run_on_open_var.get())
            )
        if self.on_save:
            self.on_save(commands)
        self._close()

    def _on_cancel(self):
        self._close()

    def _close(self):
        """Close and hand the modal grab back to the parent dialog."""
        self.grab_release()
        parent = self.master
        self.destroy()
        if isinstance(parent, tk.Toplevel) and parent.winfo_exists():
            parent.grab_set()
