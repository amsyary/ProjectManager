"""Add/Edit project dialog."""

import os
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from urllib.parse import urlparse

from models.project import Project, SubProject, ProjectType
from services.project_service import ProjectService
from ui.icon_loader import load_icon
from ui.theme import ThemeManager


class AddEditDialog(tk.Toplevel):
    """Modal dialog for adding or editing a project."""

    def __init__(self, parent, project: Project | None = None, on_save=None):
        super().__init__(parent)
        self.project = project
        self.on_save = on_save
        self.result: Project | None = None

        self.title("Edit Project" if project else "Add Project")
        self.geometry("800x560")
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_on_parent(parent)
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
            row=1, column=0, sticky="nw", pady=2
        )
        icon_section = ttk.Frame(main)
        icon_section.grid(row=1, column=1, sticky="ew", padx=8, pady=2)

        preview_frame = ttk.Frame(icon_section)
        preview_frame.pack(side="left", padx=(0, 12))
        self._icon_preview = tk.Label(preview_frame, text="(no icon)", width=8, height=3,
                                      bg=_c["bg"], fg=_c["fg"])
        self._icon_preview.pack()
        self._icon_preview_image = None

        icon_controls = ttk.Frame(icon_section)
        icon_controls.pack(side="left", fill="x", expand=True)
        self._icon_var = tk.StringVar()
        self._icon_var.trace_add("write", lambda *_: self._update_icon_preview())
        ttk.Entry(icon_controls, textvariable=self._icon_var, width=25).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(icon_controls, text="Browse...", command=self._browse_icon).pack(
            side="left", padx=2
        )
        ttk.Button(
            icon_controls, text="Choose default...", command=self._choose_default_icon
        ).pack(side="left", padx=2)

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
        sub_header = ttk.Frame(main)
        sub_header.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Label(sub_header, text="Sub-projects:").pack(side="left")
        ttk.Button(
            sub_header,
            text="+ Add sub-project",
            command=lambda: self._add_sub_row(type_value="General"),
        ).pack(side="right")

        # Scrollable container for sub-projects
        sub_container = ttk.Frame(main)
        sub_container.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=4)
        _c = ThemeManager().colors
        self.configure(bg=_c["bg"])
        self._sub_canvas = tk.Canvas(sub_container, highlightthickness=0, bg=_c["bg"])
        self._sub_scrollbar = ttk.Scrollbar(sub_container, orient="vertical", command=self._sub_canvas.yview)
        self._sub_frame = ttk.Frame(self._sub_canvas)
        self._sub_frame.bind(
            "<Configure>",
            lambda e: self._sub_canvas.configure(scrollregion=self._sub_canvas.bbox("all")),
        )
        self._sub_canvas_window = self._sub_canvas.create_window((0, 0), window=self._sub_frame, anchor="nw")
        self._sub_canvas.configure(yscrollcommand=self._sub_scrollbar.set)
        self._sub_canvas.pack(side="left", fill="both", expand=True)
        self._sub_scrollbar.pack(side="right", fill="y")
        self._sub_canvas.bind("<Configure>", self._on_sub_canvas_configure)
        for widget in (self._sub_frame, self._sub_canvas):
            widget.bind("<MouseWheel>", self._on_sub_mousewheel)
            widget.bind("<Button-4>", self._on_sub_mousewheel)  # Linux scroll up
            widget.bind("<Button-5>", self._on_sub_mousewheel)  # Linux scroll down

        self._sub_rows: list[tuple[ttk.Frame, ttk.Label, tk.StringVar, tk.StringVar, tk.StringVar, str | None]] = []

        main.rowconfigure(5, weight=1)
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="left", padx=4)

        main.columnconfigure(1, weight=1)
        self._update_icon_preview()

    def _on_sub_canvas_configure(self, event) -> None:
        """Keep inner frame width matched to canvas."""
        self._sub_canvas.itemconfig(self._sub_canvas_window, width=event.width)

    def _on_sub_mousewheel(self, event) -> None:
        """Scroll sub-projects with mouse wheel."""
        num = getattr(event, "num", None)
        if num == 4:  # Linux scroll up
            self._sub_canvas.yview_scroll(-1, "units")
        elif num == 5:  # Linux scroll down
            self._sub_canvas.yview_scroll(1, "units")
        else:  # Windows, macOS
            delta = getattr(event, "delta", 0)
            self._sub_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _center_on_parent(self, parent: tk.Tk | tk.Toplevel) -> None:
        """Position this dialog centered over the parent window."""
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw, dh = 800, 560
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        if pw > 50 and ph > 50:
            x = px + (pw - dw) // 2
            y = py + (ph - dh) // 2
        else:
            x = (sw - dw) // 2
            y = (sh - dh) // 2
        x = max(0, min(x, sw - dw))
        y = max(0, min(y, sh - dh))
        self.geometry(f"{dw}x{dh}+{x}+{y}")

    def _load_project(self):
        self._name_var.set(self.project.name)
        self._icon_var.set(self.project.icon_path or "")
        self._main_folder_var.set(self.project.main_project_folder or "")
        for sp in self.project.sub_projects:
            self._add_sub_row(
                directory=sp.directory,
                type_value=ProjectType.display_name(sp.type),
                sub_project_id=sp.id,
                name=sp.name or "",
            )

    def _renumber_sub_rows(self) -> None:
        """Update the number labels for all sub-project rows."""
        for i, (row, num_label, *_) in enumerate(self._sub_rows, start=1):
            num_label.config(text=str(i))

    def _add_sub_row(
        self,
        directory: str = "",
        type_value: str = "general",
        sub_project_id: str | None = None,
        name: str = "",
    ):
        row = ttk.Frame(self._sub_frame)
        row.pack(fill="x", pady=2)

        name_var = tk.StringVar(value=name)
        dir_var = tk.StringVar(value=directory)
        type_var = tk.StringVar(value=type_value)
        row._sp_id = sub_project_id  # Preserve id when editing

        num_label = ttk.Label(row, text="1", width=3, anchor="e")
        num_label.pack(side="left", padx=(0, 4))

        ttk.Label(row, text="Name:", width=5).pack(side="left", padx=(0, 2))
        ttk.Entry(row, textvariable=name_var, width=18).pack(side="left", padx=(0, 4))

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
                ProjectType.display_name(ProjectType.EXECUTE),
                ProjectType.display_name(ProjectType.LINK),
            ],
            state="readonly",
            width=18,
        )
        type_combo.pack(side="left", padx=4)

        def remove():
            row.destroy()
            self._sub_rows[:] = [
                (r, nl, nv, d, t, sid) for r, nl, nv, d, t, sid in self._sub_rows if r != row
            ]
            self._renumber_sub_rows()

        ttk.Button(row, text="Remove", command=remove).pack(side="left", padx=4)

        self._sub_rows.append((row, num_label, name_var, dir_var, type_var, sub_project_id))
        self._renumber_sub_rows()

    def _browse_path(self, path_var: tk.StringVar, type_var: tk.StringVar):
        display = type_var.get()
        if display == ProjectType.display_name(ProjectType.LINK):
            url = simpledialog.askstring(
                "Enter URL",
                "Enter the URL to open in browser:",
                initialvalue=path_var.get() or "https://",
            )
            if url:
                path_var.set(url.strip())
            return

        if display == ProjectType.display_name(ProjectType.DATA_TXT):
            path = filedialog.askopenfilename(
                title="Select text file",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
        elif display == ProjectType.display_name(ProjectType.EXECUTE):
            path = filedialog.askopenfilename(
                title="Select file to open or run",
                filetypes=[("All files", "*.*")],
            )
        else:
            # Flutter, Admin Dashboard, etc.: folder opens in Cursor / VS Code (file picker cannot select folders)
            path = filedialog.askdirectory(title="Select project folder")
        if path:
            path_var.set(path)

    def _update_icon_preview(self) -> None:
        """Update the icon preview based on current icon_path."""
        path = self._icon_var.get().strip() or None
        self._icon_preview_image = None
        if path:
            resolved = ProjectService.resolve_icon_path(path)
            if resolved:
                img = load_icon(str(resolved), (48, 48))
                if img:
                    self._icon_preview_image = img
                    self._icon_preview.config(image=img, text="")
                    return
        self._icon_preview.config(image="", text="(no icon)")

    def _browse_icon(self):
        path = filedialog.askopenfilename(
            title="Select project icon",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif"), ("All", "*.*")],
        )
        if path:
            self._icon_var.set(path)

    def _choose_default_icon(self):
        """Open a popup to choose from default icons."""
        default_dir = ProjectService.default_icons_dir()
        if not default_dir.exists():
            messagebox.showinfo("Default Icons", "No default icons found.")
            return

        icons = sorted(
            f for f in default_dir.iterdir()
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")
        )
        if not icons:
            messagebox.showinfo("Default Icons", "No default icons found.")
            return

        popup = tk.Toplevel(self)
        popup.title("Choose default icon")
        popup.transient(self)
        popup.grab_set()
        c = ThemeManager().colors
        popup.configure(bg=c["bg"])

        inner = ttk.Frame(popup, padding=10)
        inner.pack()

        ttk.Label(inner, text="Click an icon to select:").pack(anchor="w", pady=(0, 8))

        grid_frame = ttk.Frame(inner)
        grid_frame.pack()

        for i, icon_path in enumerate(icons):
            row, col = i // 6, i % 6
            img = load_icon(str(icon_path), (40, 40))
            if img:
                btn = tk.Button(
                    grid_frame, image=img, cursor="hand2",
                    command=lambda p=icon_path: self._on_default_icon_selected(popup, p),
                    bg=c["bg"], activebackground=c["select_bg"],
                    relief="flat", bd=1,
                )
                btn.image = img
                btn.grid(row=row, column=col, padx=4, pady=4)

        def on_cancel():
            popup.grab_release()
            popup.destroy()

        ttk.Button(inner, text="Cancel", command=on_cancel).pack(pady=(12, 0))
        popup.protocol("WM_DELETE_WINDOW", on_cancel)

    def _on_default_icon_selected(self, popup: tk.Toplevel, icon_path: Path) -> None:
        """Store default icon as default_icon:filename and close popup."""
        self._icon_var.set(f"default_icon:{icon_path.name}")
        popup.grab_release()
        popup.destroy()

    def _browse_main_folder(self):
        path = filedialog.askdirectory(title="Select main project folder")
        if path:
            self._main_folder_var.set(path)

    def _display_to_type(self, display: str) -> ProjectType:
        for pt in ProjectType:
            if ProjectType.display_name(pt) == display:
                return pt
        return ProjectType.GENERAL

    def _is_valid_url(self, s: str) -> bool:
        """Check if string is a valid URL."""
        try:
            result = urlparse(s)
            return all([result.scheme, result.netloc]) and result.scheme in ("http", "https")
        except Exception:
            return False

    def _on_save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Project name is required.")
            return

        icon_path = self._icon_var.get().strip() or None
        main_project_folder = self._main_folder_var.get().strip() or None

        sub_projects = []
        for row, num_label, name_var, dir_var, type_var, sp_id in self._sub_rows:
            d = dir_var.get().strip()
            if not d:
                continue
            t = self._display_to_type(type_var.get() or "General")
            if t == ProjectType.LINK and not self._is_valid_url(d):
                messagebox.showerror(
                    "Invalid URL",
                    f"Please enter a valid URL (e.g. https://example.com) for the Link type.\n\nGot: {d[:50]}{'...' if len(d) > 50 else ''}",
                )
                return
            if t == ProjectType.EXECUTE and not os.path.isfile(d):
                messagebox.showerror(
                    "Invalid file",
                    "Execute / Open file requires an existing file path.",
                )
                return
            custom_name = name_var.get().strip() or None
            sub_projects.append(
                SubProject(
                    id=sp_id or str(uuid.uuid4()),
                    directory=d,
                    type=t,
                    name=custom_name,
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
