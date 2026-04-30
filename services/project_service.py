"""CRUD operations for projects and settings persistence."""

import json
import sys
from pathlib import Path
from typing import Optional

from models.project import Project, SubProject, TextSnippet


def _app_dir() -> Path:
    """Base directory for config and data (persistent storage)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _projects_path() -> Path:
    path = _app_dir() / "data" / "projects.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _settings_path() -> Path:
    path = _app_dir() / "config" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_settings() -> dict:
    path = _settings_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


def _write_settings(data: dict) -> None:
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class ProjectService:
    """Service for loading, saving, and managing projects."""

    def __init__(self):
        self._projects: list[Project] = []
        self._snippets: list[TextSnippet] = []
        self._load_projects()

    def _load_projects(self) -> None:
        path = _projects_path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self._projects = [
                    Project.from_dict(p) for p in data.get("projects", [])
                ]
                self._snippets = [
                    TextSnippet.from_dict(s) for s in data.get("text_snippets", [])
                ]
            except (json.JSONDecodeError, KeyError):
                self._projects = []
                self._snippets = []
        else:
            self._projects = []
            self._snippets = []
            self._save_projects()

    def _save_projects(self) -> None:
        path = _projects_path()
        data = {
            "projects": [p.to_dict() for p in self._projects],
            "text_snippets": [s.to_dict() for s in self._snippets],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_all(self) -> list[Project]:
        """Return all projects."""
        return list(self._projects)

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Return project by ID or None."""
        for p in self._projects:
            if p.id == project_id:
                return p
        return None

    def add(self, project: Project) -> None:
        """Add a new project and save."""
        self._projects.append(project)
        self._save_projects()

    def update(self, project: Project) -> bool:
        """Update an existing project. Returns True if found."""
        for i, p in enumerate(self._projects):
            if p.id == project.id:
                self._projects[i] = project
                self._save_projects()
                return True
        return False

    def delete(self, project_id: str) -> bool:
        """Delete a project by ID. Returns True if found and deleted."""
        for i, p in enumerate(self._projects):
            if p.id == project_id:
                del self._projects[i]
                self._save_projects()
                return True
        return False

    def increment_open_count(self, project_id: str) -> bool:
        """Increment open_count for project and save. Returns True if found."""
        for p in self._projects:
            if p.id == project_id:
                p.open_count += 1
                self._save_projects()
                return True
        return False

    def get_snippets(self) -> list[TextSnippet]:
        """Return all text snippets."""
        return list(self._snippets)

    def add_snippet(self, snippet: TextSnippet) -> None:
        """Add a new text snippet and save."""
        self._snippets.append(snippet)
        self._save_projects()

    def update_snippet(self, snippet: TextSnippet) -> bool:
        """Update an existing text snippet. Returns True if found."""
        for i, s in enumerate(self._snippets):
            if s.id == snippet.id:
                self._snippets[i] = snippet
                self._save_projects()
                return True
        return False

    def delete_snippet(self, snippet_id: str) -> bool:
        """Delete a text snippet by ID. Returns True if found and deleted."""
        for i, s in enumerate(self._snippets):
            if s.id == snippet_id:
                del self._snippets[i]
                self._save_projects()
                return True
        return False

    def export_to_file(self, path: str | Path) -> bool:
        """Export projects and snippets to a JSON file. Returns True on success."""
        try:
            data = {
                "projects": [p.to_dict() for p in self._projects],
                "text_snippets": [s.to_dict() for s in self._snippets],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except (OSError, TypeError):
            return False

    def import_from_file(self, path: str | Path) -> list[Project] | None:
        """Load projects from a JSON file. Returns list of projects or None on error."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return [Project.from_dict(p) for p in data.get("projects", [])]
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def replace_all(self, projects: list[Project]) -> None:
        """Replace all projects with the given list and save."""
        self._projects = list(projects)
        self._save_projects()

    def merge_projects(self, projects: list[Project]) -> None:
        """Merge imported projects: update existing by id, add new ones."""
        existing_ids = {p.id for p in self._projects}
        for proj in projects:
            if proj.id in existing_ids:
                self.update(proj)
            else:
                self._projects.append(proj)
                existing_ids.add(proj.id)
        self._save_projects()

    @staticmethod
    def get_editor() -> str:
        """Get saved editor preference (cursor, code, or antigravity)."""
        return _read_settings().get("editor", "cursor")

    @staticmethod
    def set_editor(editor: str) -> None:
        """Save editor preference."""
        data = _read_settings()
        data["editor"] = editor.lower() if editor else "cursor"
        _write_settings(data)

    @staticmethod
    def get_theme() -> str:
        """Get saved theme preference ('light' or 'dark')."""
        return _read_settings().get("theme", "light")

    @staticmethod
    def set_theme(theme: str) -> None:
        """Save theme preference ('light' or 'dark')."""
        data = _read_settings()
        data["theme"] = theme
        _write_settings(data)

    @staticmethod
    def icons_dir() -> Path:
        """Path to the assets/icons directory."""
        if getattr(sys, "frozen", False):
            return Path(sys._MEIPASS) / "assets" / "icons"
        return _app_dir() / "assets" / "icons"

    @staticmethod
    def default_icons_dir() -> Path:
        """Path to the assets/icons/default_icon directory."""
        return ProjectService.icons_dir() / "default_icon"

    @staticmethod
    def resolve_icon_path(icon_path: str | None) -> Path | None:
        """
        Resolve icon path. If it starts with 'default_icon:', resolve from default_icons_dir.
        Otherwise return the path as-is if it exists.
        """
        if not icon_path:
            return None
        if icon_path.startswith("default_icon:"):
            filename = icon_path[len("default_icon:"):]
            resolved = ProjectService.default_icons_dir() / filename
            return resolved if resolved.exists() else None
        p = Path(icon_path)
        return p if p.exists() else None
