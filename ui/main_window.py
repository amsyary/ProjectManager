"""Main application window with grid view and top bar."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from models.project import Project
from services.project_service import ProjectService
from ui.project_card import ProjectCard
from ui.add_edit_dialog import AddEditDialog
from ui.sub_project_panel import SubProjectPanel
from ui.text_panel import TextPanel
from ui.theme import ThemeManager


class MainWindow:
    """Main application window."""

    GRID_COLS = 4

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Project Manager")
        self.root.geometry("950x600")
        self.root.minsize(700, 400)

        self._project_service = ProjectService()
        self._selected_project: Project | None = None
        self._card_widgets: list[ProjectCard] = []
        self._texts_visible = False

        ThemeManager().init(self.root, dark=ProjectService.get_theme() == "dark")
        self._build_ui()
        self._apply_tk_theme()
        self._refresh_grid()

    def _build_ui(self):
        self._build_menu()

        top_bar = ttk.Frame(self.root, padding=8)
        top_bar.pack(fill="x")

        ttk.Label(top_bar, text="Editor:").pack(side="left", padx=(0, 8))
        saved = ProjectService.get_editor()
        self._editor_var = tk.StringVar(value=saved)
        self._editor_display = {
            "Cursor": "cursor",
            "VS Code": "code",
            "Antigravity": "antigravity",
        }
        self._editor_reverse = {v: k for k, v in self._editor_display.items()}
        editor_combo = ttk.Combobox(
            top_bar,
            textvariable=self._editor_var,
            values=list(self._editor_display.keys()),
            state="readonly",
            width=14,
        )
        self._editor_var.set(self._editor_reverse.get(saved, "Cursor"))
        editor_combo.pack(side="left", padx=(0, 16))
        editor_combo.bind("<<ComboboxSelected>>", self._on_editor_change)

        self._texts_btn = ttk.Button(top_bar, text="Texts ▶", command=self._toggle_text_panel)
        self._texts_btn.pack(side="right", padx=(0, 4))

        _theme_label = "Light Mode" if ThemeManager().is_dark else "Night Mode"
        self._theme_btn = ttk.Button(top_bar, text=_theme_label, command=self._toggle_theme)
        self._theme_btn.pack(side="right", padx=(0, 8))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        self._content = ttk.PanedWindow(self.root, orient="horizontal")
        self._content.pack(fill="both", expand=True, padx=8, pady=8)

        self._left_frame = ttk.Frame(self._content)
        self._content.add(self._left_frame, weight=2)
        left_frame = self._left_frame

        grid_header = ttk.Frame(left_frame)
        grid_header.pack(fill="x")
        ttk.Label(grid_header, text="Projects", font=("", 12, "bold")).pack(side="left")
        ttk.Button(
            grid_header, text="+ Add Project", command=self._on_add_project
        ).pack(side="right", padx=4)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh_grid())
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill="x", pady=(4, 0))
        ttk.Label(search_frame, text="Search:").pack(side="left", padx=(0, 4))
        search_entry = ttk.Entry(
            search_frame, textvariable=self._search_var, width=30
        )
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        canvas_frame = ttk.Frame(left_frame)
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=self._canvas.yview)

        self._grid_inner = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._grid_inner, anchor="nw"
        )

        self._grid_inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(
                self._canvas_window, width=e.width
            ),
        )
        # Wheel goes to the widget under the cursor (cards), not the canvas — bind the whole left column.
        self._bind_wheel_scroll_tree(left_frame)
        self._canvas.bind("<MouseWheel>", self._on_grid_mousewheel)
        self._canvas.bind("<Button-4>", self._on_grid_mousewheel)
        self._canvas.bind("<Button-5>", self._on_grid_mousewheel)

        self._sub_panel = SubProjectPanel(
            self._content,
            on_sub_project_opened=self._on_sub_project_opened,
            on_edit_project=self._on_edit_project,
        )
        self._content.add(self._sub_panel, weight=1)

        self._text_panel = TextPanel(self._content, self._project_service)

    def _toggle_text_panel(self):
        if self._texts_visible:
            self._content.remove(self._text_panel)
            self._texts_visible = False
            self._texts_btn.config(text="Texts ▶")
        else:
            self._content.add(self._text_panel, weight=1)
            self._texts_visible = True
            self._texts_btn.config(text="Texts ◀")
            self._text_panel.refresh()
            current_w = self.root.winfo_width()
            if current_w < 1200:
                self.root.geometry(f"1300x{self.root.winfo_height()}")

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export...", command=self._on_export)
        file_menu.add_command(label="Import...", command=self._on_import)

    def _on_export(self):
        path = filedialog.asksaveasfilename(
            title="Export projects",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        if self._project_service.export_to_file(path):
            messagebox.showinfo("Export", "Projects exported successfully.")
        else:
            messagebox.showerror("Export", "Failed to export projects.")

    def _on_import(self):
        path = filedialog.askopenfilename(
            title="Import projects",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        projects = self._project_service.import_from_file(path)
        if projects is None:
            messagebox.showerror("Import", "Failed to load file. Invalid or corrupted.")
            return

        current_count = len(self._project_service.get_all())
        if current_count == 0:
            self._project_service.replace_all(projects)
            self._selected_project = None
            self._sub_panel.set_project(None)
            self._refresh_grid()
            messagebox.showinfo("Import", f"Imported {len(projects)} project(s).")
            return

        result = messagebox.askyesnocancel(
            "Import",
            f"Import {len(projects)} project(s).\n\n"
            f"You have {current_count} current project(s).\n\n"
            "Yes = Overwrite (replace all current projects)\n"
            "No = Merge (add/update, keep existing)\n"
            "Cancel = Abort",
        )
        if result is None:
            return

        if result:
            if not messagebox.askyesno(
                "Confirm Overwrite",
                f"This will replace all {current_count} current project(s) with "
                f"{len(projects)} imported project(s).\n\nContinue?",
            ):
                return
            self._project_service.replace_all(projects)
        else:
            self._project_service.merge_projects(projects)

        self._selected_project = None
        self._sub_panel.set_project(None)
        self._refresh_grid()
        messagebox.showinfo("Import", f"Imported {len(projects)} project(s).")

    def _on_grid_mousewheel(self, event: tk.Event) -> None:
        """Scroll project grid; bound on canvas and recursively on grid widgets."""
        num = getattr(event, "num", None)
        if num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            delta = getattr(event, "delta", 0)
            if delta:
                self._canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _bind_wheel_scroll_tree(self, widget: tk.Widget) -> None:
        """So wheel works when the pointer is over project cards, not only the scrollbar."""
        widget.bind("<MouseWheel>", self._on_grid_mousewheel)
        widget.bind("<Button-4>", self._on_grid_mousewheel)
        widget.bind("<Button-5>", self._on_grid_mousewheel)
        for child in widget.winfo_children():
            self._bind_wheel_scroll_tree(child)

    def _on_editor_change(self, event=None):
        display = self._editor_var.get()
        editor = self._editor_display.get(display, "cursor")
        ProjectService.set_editor(editor)
        self._sub_panel.refresh_editor()

    def _on_sub_project_opened(self, project: Project) -> None:
        self._project_service.increment_open_count(project.id)
        self._refresh_grid()

    def _refresh_grid(self):
        for w in self._card_widgets:
            w.destroy()
        self._card_widgets.clear()

        for w in self._grid_inner.winfo_children():
            w.destroy()

        projects = self._project_service.get_all()
        search = self._search_var.get().strip().lower()
        if search:
            projects = [p for p in projects if search in p.name.lower()]
        projects.sort(key=lambda p: p.open_count, reverse=True)

        for i, project in enumerate(projects):
            row = i // self.GRID_COLS
            col = i % self.GRID_COLS
            is_selected = self._selected_project and self._selected_project.id == project.id
            card = ProjectCard(
                self._grid_inner,
                project,
                on_click=self._on_project_click,
                on_edit=self._on_edit_project,
                on_delete=self._on_delete_project,
                is_selected=is_selected,
            )
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self._card_widgets.append(card)

        for c in range(self.GRID_COLS):
            self._grid_inner.columnconfigure(c, weight=1)

        # New cards are recreated each refresh; re-bind wheel on the grid subtree only.
        self._bind_wheel_scroll_tree(self._grid_inner)

    def _on_add_project(self):
        def on_save(project: Project):
            self._project_service.add(project)
            self._refresh_grid()

        AddEditDialog(self.root, project=None, on_save=on_save)

    def _on_project_click(self, project: Project):
        self._selected_project = project
        for card in self._card_widgets:
            card.set_selected(card.project.id == project.id)
        self._sub_panel.set_project(project)

    def _on_edit_project(self, project: Project):
        def on_save(updated: Project):
            self._project_service.update(updated)
            self._refresh_grid()
            if self._selected_project and self._selected_project.id == updated.id:
                self._sub_panel.set_project(updated)

        AddEditDialog(self.root, project=project, on_save=on_save)

    def _on_delete_project(self, project: Project):
        if not messagebox.askyesno(
            "Delete Project",
            f"Delete project '{project.name}'? This cannot be undone.",
        ):
            return
        self._project_service.delete(project.id)
        if self._selected_project and self._selected_project.id == project.id:
            self._selected_project = None
            self._sub_panel.set_project(None)
        self._refresh_grid()

    def _toggle_theme(self) -> None:
        is_dark = ThemeManager().toggle()
        ProjectService.set_theme("dark" if is_dark else "light")
        self._theme_btn.config(text="Light Mode" if is_dark else "Night Mode")
        self._apply_tk_theme()
        self._refresh_grid()
        self._text_panel.apply_theme()

    def _apply_tk_theme(self) -> None:
        c = ThemeManager().colors
        self.root.configure(bg=c["bg"])
        self._canvas.configure(bg=c["bg"], highlightbackground=c["bg"])

    def run(self):
        self.root.mainloop()
