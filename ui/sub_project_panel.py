"""Panel showing sub-projects of a selected project with Open buttons."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from models.project import Project, SubProject, ProjectType
from services.project_service import ProjectService
from services.editor_launcher import EditorLauncher
from services.terminal_launcher import TerminalLauncher, TERMINALS
from ui.icon_loader import load_icon, load_type_icon
from ui.theme import ThemeManager

MAX_DIR_DISPLAY = 35


def _create_tooltip(widget: tk.Widget, text: str, delay_ms: int = 500) -> None:
    """Show tooltip with full text after hovering for delay_ms."""
    tooltip: tk.Toplevel | None = None
    after_id: str | None = None

    def show():
        nonlocal tooltip
        if tooltip:
            return
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry("+0+0")
        c = ThemeManager().colors
        lbl = tk.Label(
            tooltip,
            text=text,
            justify="left",
            background=c["tooltip_bg"],
            foreground=c["tooltip_fg"],
            relief="solid",
            borderwidth=1,
            padx=4,
            pady=2,
            wraplength=400,
        )
        lbl.pack()
        x = widget.winfo_rootx() + 10
        y = widget.winfo_rooty() + widget.winfo_height() + 2
        tooltip.wm_geometry(f"+{x}+{y}")

    def hide():
        nonlocal tooltip, after_id
        if after_id:
            widget.after_cancel(after_id)
            after_id = None
        if tooltip:
            tooltip.destroy()
            tooltip = None

    def on_enter(_):
        nonlocal after_id
        after_id = widget.after(delay_ms, show)

    def on_leave(_):
        hide()

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


class SubProjectPanel(ttk.Frame):
    """Displays sub-projects with type icon, directory name, and Open button."""

    def __init__(
        self,
        parent,
        on_sub_project_opened: Callable[[Project], None] | None = None,
        on_edit_project: Callable[[Project], None] | None = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self._icons_dir = ProjectService.icons_dir()
        self._editor = EditorLauncher(ProjectService.get_editor())
        self._terminal = TerminalLauncher(ProjectService.get_terminal())
        self._project: Project | None = None
        self._on_sub_project_opened = on_sub_project_opened
        self._on_edit_project = on_edit_project
        self._build_ui()

    def _build_ui(self):
        self._title_frame = ttk.Frame(self)
        self._title_frame.pack(anchor="w", padx=4, pady=4)
        self._title_icon = ttk.Label(self._title_frame)
        self._title_icon.pack(side="left", padx=(0, 6))
        self._title_icon_image = None
        self._title = ttk.Label(self._title_frame, text="", font=("", 10, "bold"))
        self._title.pack(side="left")

        self._list_frame = ttk.Frame(self)
        self._list_frame.pack(fill="both", expand=True)

        self._empty_label = ttk.Label(
            self._list_frame, text="Select a project to see sub-projects"
        )
        self._empty_label.pack(pady=20)

    def set_project(self, project: Project | None) -> None:
        """Display sub-projects for the given project."""
        self._project = project
        for w in self._list_frame.winfo_children():
            w.destroy()

        if project is None:
            self._title_icon.config(image="")
            self._title_icon_image = None
            self._title.config(text="")
            self._empty_label = ttk.Label(
                self._list_frame, text="Select a project to see sub-projects"
            )
            self._empty_label.pack(pady=20)
            return

        self._title.config(text=f"Sub-projects: {project.name}")
        self._title_icon_image = None
        if project.icon_path:
            img = load_icon(project.icon_path, (32, 32))
            if img:
                self._title_icon_image = img
                self._title_icon.config(image=img)
            else:
                self._title_icon.config(image="")
        else:
            self._title_icon.config(image="")

        has_main_folder = bool(project.main_project_folder)
        has_sub_projects = bool(project.sub_projects)

        btn_bar = ttk.Frame(self._list_frame)
        btn_bar.pack(fill="x", pady=(0, 8))

        def open_project_folder():
            if project.main_project_folder:
                self._editor.open_in_explorer(project.main_project_folder)
            else:
                messagebox.showinfo(
                    "Project Folder",
                    "Project folder is not set. Edit the project to add a main project folder.",
                )

        ttk.Button(
            btn_bar, text="Project Folder", command=open_project_folder
        ).pack(side="left", padx=(0, 8))

        if has_main_folder:
            ttk.Button(
                btn_bar, text="Terminal",
                command=lambda: self._open_terminal(project.main_project_folder),
            ).pack(side="left", padx=(0, 8))

        def edit_project():
            if self._on_edit_project:
                self._on_edit_project(project)

        ttk.Button(btn_bar, text="Edit Project", command=edit_project).pack(
            side="left", padx=(0, 8)
        )

        if has_sub_projects:
            def open_all():
                for sp in project.sub_projects:
                    self._open_sub_project(sp)
                    if self._on_sub_project_opened:
                        self._on_sub_project_opened(project)

            ttk.Button(btn_bar, text="Open All", command=open_all).pack(side="left")

        if has_sub_projects:
            for sp in project.sub_projects:
                self._add_sub_project_row(sp, project)
        else:
            ttk.Label(self._list_frame, text="No sub-projects added.").pack(pady=10)

    def _add_sub_project_row(self, sp: SubProject, project: Project) -> None:
        row = ttk.Frame(self._list_frame)
        row.pack(fill="x", padx=4, pady=2)

        icon = load_type_icon(self._icons_dir, sp.type.value, (24, 24))
        if icon:
            icon_lbl = ttk.Label(row, image=icon)
            icon_lbl.image = icon
            icon_lbl.pack(side="left", padx=(0, 8), pady=4)
        else:
            ttk.Label(row, text=ProjectType.display_name(sp.type)[:1]).pack(
                side="left", padx=(0, 8)
            )

        display_text = sp.display_name()
        if len(display_text) > MAX_DIR_DISPLAY:
            display_text = display_text[: MAX_DIR_DISPLAY - 3] + "..."

        def open_cmd():
            self._open_sub_project(sp)
            if self._on_sub_project_opened:
                self._on_sub_project_opened(project)

        open_btn = ttk.Button(row, text="Open", command=open_cmd, width=8)
        open_btn.pack(side="right")

        if sp.type != ProjectType.LINK:
            if len(sp.commands) == 1:
                cmd = sp.commands[0]
                run_btn = ttk.Button(
                    row, text="Run", width=6,
                    command=lambda: self._open_terminal(sp.directory, cmd.command),
                )
                run_btn.pack(side="right", padx=(0, 4))
                _create_tooltip(run_btn, f"Run in terminal: {cmd.command}")
            elif sp.commands:
                run_btn = ttk.Button(row, text="Run ▾", width=6)
                run_btn.config(command=lambda: self._show_run_menu(run_btn, sp))
                run_btn.pack(side="right", padx=(0, 4))
            ttk.Button(
                row, text="Terminal", width=8,
                command=lambda: self._open_terminal(sp.directory),
            ).pack(side="right", padx=(0, 4))

        name_label = ttk.Label(row, text=display_text)
        name_label.pack(side="left", padx=(0, 8))
        _create_tooltip(name_label, sp.directory)

    def _show_run_menu(self, button: ttk.Button, sp: SubProject) -> None:
        """Drop-down under the Run button to pick which command to run."""
        menu = tk.Menu(self, tearoff=0)
        for c in sp.commands:
            label = c.display_name()
            if c.name and c.name.strip():
                label = f"{label}   ({c.command})"
            menu.add_command(
                label=label,
                command=lambda c=c: self._open_terminal(sp.directory, c.command),
            )
        menu.add_separator()
        menu.add_command(
            label="Run all",
            command=lambda: [self._open_terminal(sp.directory, c.command) for c in sp.commands],
        )
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())

    def _open_sub_project(self, sp: SubProject) -> None:
        """Open in the editor/app, and start any commands marked Run when opened."""
        self._editor.open(sp.directory, sp.type)
        if sp.type != ProjectType.LINK:
            for c in sp.commands:
                if c.run_on_open:
                    self._open_terminal(sp.directory, c.command)

    def _open_terminal(self, path: str, command: str | None = None) -> None:
        """Open path in the chosen terminal (running command if given); show an error on failure."""
        if not self._terminal.open(path, command):
            messagebox.showerror(
                "Terminal",
                f"Could not open {TERMINALS[self._terminal.terminal]} in:\n{path}\n\n"
                "Check that the folder exists and the terminal is installed.",
            )

    def refresh_editor(self) -> None:
        """Refresh editor preference (e.g. after user changes it)."""
        self._editor = EditorLauncher(ProjectService.get_editor())

    def refresh_terminal(self) -> None:
        """Refresh terminal preference (e.g. after user changes it)."""
        self._terminal = TerminalLauncher(ProjectService.get_terminal())
