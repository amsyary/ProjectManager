"""CRUD operations for projects and settings persistence."""

import json
import sys
from pathlib import Path
from typing import Optional

from models.project import Project, SubProject


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


class ProjectService:
    """Service for loading, saving, and managing projects."""

    def __init__(self):
        self._projects: list[Project] = []
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
            except (json.JSONDecodeError, KeyError):
                self._projects = []
        else:
            self._projects = []
            self._save_projects()

    def _save_projects(self) -> None:
        path = _projects_path()
        data = {"projects": [p.to_dict() for p in self._projects]}
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

    def export_to_file(self, path: str | Path) -> bool:
        """Export projects to a JSON file. Returns True on success."""
        try:
            data = {"projects": [p.to_dict() for p in self._projects]}
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
        """Get saved editor preference (cursor or code)."""
        path = _settings_path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("editor", "cursor")
            except (json.JSONDecodeError, KeyError):
                pass
        return "cursor"

    @staticmethod
    def set_editor(editor: str) -> None:
        """Save editor preference."""
        path = _settings_path()
        data = {"editor": editor.lower() if editor else "cursor"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

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
