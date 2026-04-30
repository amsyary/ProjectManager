"""Panel for managing and copying saved text snippets."""

import tkinter as tk
from tkinter import ttk, messagebox
import uuid

from models.project import TextSnippet
from services.project_service import ProjectService
from ui.theme import ThemeManager


class TextPanel(ttk.Frame):
    """Right-side panel for text snippet management."""

    def __init__(self, parent, project_service: ProjectService, **kwargs):
        super().__init__(parent, **kwargs)
        self._service = project_service
        self._build_ui()

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=6, pady=(6, 4))
        ttk.Label(header, text="Text Snippets", font=("", 10, "bold")).pack(side="left")
        ttk.Button(header, text="+ Add", command=self._on_add).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True)

        self._scrollbar = ttk.Scrollbar(canvas_frame)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas = tk.Canvas(canvas_frame, highlightthickness=0, yscrollcommand=self._scrollbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.configure(command=self._canvas.yview)
        c = ThemeManager().colors
        self._canvas.configure(bg=c["bg"], highlightbackground=c["bg"])

        self._inner = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width),
        )
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)

        self.refresh()

    def _on_mousewheel(self, event: tk.Event) -> None:
        num = getattr(event, "num", None)
        if num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            delta = getattr(event, "delta", 0)
            if delta:
                self._canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _bind_mousewheel(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel(child)

    def refresh(self) -> None:
        for w in self._inner.winfo_children():
            w.destroy()

        snippets = self._service.get_snippets()
        if not snippets:
            ttk.Label(
                self._inner,
                text="No text snippets yet.\nClick '+ Add' to create one.",
                justify="center",
                foreground="gray",
            ).pack(pady=24)
            return

        for snippet in snippets:
            self._add_snippet_card(snippet)

    def _add_snippet_card(self, snippet: TextSnippet) -> None:
        outer = ttk.Frame(self._inner, relief="solid", borderwidth=1)
        outer.pack(fill="x", padx=8, pady=4)

        lines = snippet.content.count("\n") + 1
        height = min(max(lines, 2), 12)

        c = ThemeManager().colors
        txt = tk.Text(
            outer,
            wrap="word",
            height=height,
            relief="flat",
            borderwidth=0,
            padx=6,
            pady=4,
            cursor="arrow",
            state="normal",
            bg=c["bg"],
            fg=c["fg"],
            insertbackground=c["fg"],
            selectbackground=c["select_bg"],
            selectforeground=c["select_fg"],
        )
        txt.insert("1.0", snippet.content)
        txt.config(state="disabled")
        txt.pack(fill="x", padx=2, pady=(4, 0))

        btn_bar = ttk.Frame(outer)
        btn_bar.pack(fill="x", padx=6, pady=(2, 6))

        def on_copy(s=snippet):
            self.clipboard_clear()
            self.clipboard_append(s.content)

        def on_edit(s=snippet):
            self._open_edit_dialog(s)

        def on_delete(s=snippet):
            if messagebox.askyesno(
                "Delete Snippet",
                "Delete this text snippet?",
                parent=self.winfo_toplevel(),
            ):
                self._service.delete_snippet(s.id)
                self.refresh()

        ttk.Button(btn_bar, text="Copy", command=on_copy, width=6).pack(side="right", padx=(4, 0))
        ttk.Button(btn_bar, text="Edit", command=on_edit, width=6).pack(side="right", padx=(4, 0))
        ttk.Button(btn_bar, text="Del", command=on_delete, width=4).pack(side="right")

        # Bind scroll on all card children so wheel works over cards too
        self._bind_mousewheel(outer)

    def apply_theme(self) -> None:
        c = ThemeManager().colors
        self._canvas.configure(bg=c["bg"], highlightbackground=c["bg"])
        self.refresh()

    def _on_add(self):
        self._open_edit_dialog(None)

    def _open_edit_dialog(self, snippet: TextSnippet | None) -> None:
        root = self.winfo_toplevel()
        dialog = tk.Toplevel(root)
        dialog.title("Add Text Snippet" if snippet is None else "Edit Text Snippet")
        dialog.transient(root)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.geometry("480x300")
        dialog.minsize(320, 200)
        c = ThemeManager().colors
        dialog.configure(bg=c["bg"])

        btn_bar = ttk.Frame(dialog)
        btn_bar.pack(side="bottom", fill="x", padx=12, pady=12)

        ttk.Label(dialog, text="Text content:").pack(padx=12, pady=(12, 4), anchor="w")

        txt_frame = ttk.Frame(dialog)
        txt_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        sb = ttk.Scrollbar(txt_frame)
        sb.pack(side="right", fill="y")
        txt = tk.Text(
            txt_frame, wrap="word", yscrollcommand=sb.set,
            bg=c["bg_input"], fg=c["fg"],
            insertbackground=c["fg"],
            selectbackground=c["select_bg"],
            selectforeground=c["select_fg"],
        )
        sb.config(command=txt.yview)
        txt.pack(fill="both", expand=True)
        if snippet:
            txt.insert("1.0", snippet.content)
        txt.focus_set()

        def on_save():
            content = txt.get("1.0", "end-1c")
            if not content.strip():
                messagebox.showwarning("Empty", "Text content cannot be empty.", parent=dialog)
                return
            if snippet is None:
                self._service.add_snippet(TextSnippet(id=str(uuid.uuid4()), content=content))
            else:
                snippet.content = content
                self._service.update_snippet(snippet)
            self.refresh()
            dialog.destroy()

        ttk.Button(btn_bar, text="Save", command=on_save).pack(side="right", padx=(8, 0))
        ttk.Button(btn_bar, text="Cancel", command=dialog.destroy).pack(side="right")
        dialog.bind("<Escape>", lambda _: dialog.destroy())
