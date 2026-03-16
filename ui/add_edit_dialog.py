"""Add/Edit project dialog."""

import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from models.project import Project, SubProject, ProjectType


class AddEditDialog(tk.Toplevel):
    """Modal dialog for adding or editing a project."""

    def __init__(self, parent, project: Project | None = None, on_save=None):
        super().__init__(parent)
        self.project = project
        self.on_save = on_save
        self.result: Project | None = None

        self.title("Edit Project" if project else "Add Project")
        self.geometry("500x450")
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        if project:
            self._load_project()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Project name:").grid(row=0, column=0, sticky="w", pady=2)
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(main, textvariable=self._name_var, width=40)
        self._name_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=2)

        ttk.Label(main, text="Project icon (optional):").grid(
            row=1, column=0, sticky="w", pady=2
        )
        icon_frame = ttk.Frame(main)
        icon_frame.grid(row=1, column=1, sticky="ew", padx=8, pady=2)
        self._icon_var = tk.StringVar()
        ttk.Entry(icon_frame, textvariable=self._icon_var, width=30).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(icon_frame, text="Browse...", command=self._browse_icon).pack(
            side="left", padx=4
        )

        ttk.Label(main, text="Main Project Folder (optional):").grid(
            row=2, column=0, sticky="w", pady=2
        )
        main_folder_frame = ttk.Frame(main)
        main_folder_frame.grid(row=2, column=1, sticky="ew", padx=8, pady=2)
        self._main_folder_var = tk.StringVar()
        ttk.Entry(main_folder_frame, textvariable=self._main_folder_var, width=30).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(
            main_folder_frame, text="Browse...", command=self._browse_main_folder
        ).pack(side="left", padx=4)

        ttk.Separator(main, orient="horizontal").grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=10
        )
        ttk.Label(main, text="Sub-projects:").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=4
        )

        self._sub_frame = ttk.Frame(main)
        self._sub_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=4)

        ttk.Button(
            self._sub_frame,
            text="+ Add sub-project",
            command=lambda: self._add_sub_row(type_value="General"),
        ).pack(anchor="w", pady=4)

        self._sub_rows: list[tuple[ttk.Frame, tk.StringVar, tk.StringVar]] = []

        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="left", padx=4)

        main.columnconfigure(1, weight=1)

    def _load_project(self):
        self._name_var.set(self.project.name)
        self._icon_var.set(self.project.icon_path or "")
        self._main_folder_var.set(self.project.main_project_folder or "")
        for sp in self.project.sub_projects:
            self._add_sub_row(
                sp.directory,
                ProjectType.display_name(sp.type),
                sp.id,
            )

    def _add_sub_row(
        self,
        directory: str = "",
        type_value: str = "general",
        sub_project_id: str | None = None,
    ):
        row = ttk.Frame(self._sub_frame)
        row.pack(fill="x", pady=2)

        dir_var = tk.StringVar(value=directory)
        type_var = tk.StringVar(value=type_value)
        row._sp_id = sub_project_id  # Preserve id when editing

        ttk.Button(
            row, text="Browse...", width=8,
            command=lambda: self._browse_path(dir_var, type_var),
        ).pack(side="left", padx=(0, 4))
        ttk.Entry(row, textvariable=dir_var, width=35).pack(side="left", fill="x", expand=True, padx=4)

        type_combo = ttk.Combobox(
            row,
            textvariable=type_var,
            values=[
                ProjectType.display_name(ProjectType.FLUTTER),
                ProjectType.display_name(ProjectType.ADMIN_DASHBOARD),
                ProjectType.display_name(ProjectType.CLOUD_FUNCTION),
                ProjectType.display_name(ProjectType.WEB_VERSION),
                ProjectType.display_name(ProjectType.DOCUMENTATION),
                ProjectType.display_name(ProjectType.GENERAL),
                ProjectType.display_name(ProjectType.DATA_TXT),
            ],
            state="readonly",
            width=18,
        )
        type_combo.pack(side="left", padx=4)

        def remove():
            row.destroy()
            self._sub_rows[:] = [
                (r, d, t, sid) for r, d, t, sid in self._sub_rows if r != row
            ]

        ttk.Button(row, text="Remove", command=remove).pack(side="left", padx=4)

        self._sub_rows.append((row, dir_var, type_var, sub_project_id))

    def _browse_path(self, path_var: tk.StringVar, type_var: tk.StringVar):
        if type_var.get() == ProjectType.display_name(ProjectType.DATA_TXT):
            path = filedialog.askopenfilename(
                title="Select .txt file",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
        else:
            path = filedialog.askdirectory(title="Select project directory")
        if path:
            path_var.set(path)

    def _browse_icon(self):
        path = filedialog.askopenfilename(
            title="Select project icon",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif"), ("All", "*.*")],
        )
        if path:
            self._icon_var.set(path)

    def _browse_main_folder(self):
        path = filedialog.askdirectory(title="Select main project folder")
        if path:
            self._main_folder_var.set(path)

    def _display_to_type(self, display: str) -> ProjectType:
        for pt in ProjectType:
            if ProjectType.display_name(pt) == display:
                return pt
        return ProjectType.GENERAL

    def _on_save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Project name is required.")
            return

        icon_path = self._icon_var.get().strip() or None
        main_project_folder = self._main_folder_var.get().strip() or None

        sub_projects = []
        for row, dir_var, type_var, sp_id in self._sub_rows:
            d = dir_var.get().strip()
            if not d:
                continue
            t = self._display_to_type(type_var.get() or "General")
            sub_projects.append(
                SubProject(
                    id=sp_id or str(uuid.uuid4()),
                    directory=d,
                    type=t,
                )
            )

        project_id = self.project.id if self.project else str(uuid.uuid4())
        open_count = self.project.open_count if self.project else 0
        self.result = Project(
            id=project_id,
            name=name,
            icon_path=icon_path,
            main_project_folder=main_project_folder,
            sub_projects=sub_projects,
            open_count=open_count,
        )

        if self.on_save:
            self.on_save(self.result)
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()
