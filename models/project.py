"""Data models for Project, SubProject, SubProjectCommand, and TextSnippet."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid


class ProjectType(str, Enum):
    """Type of sub-project for visual categorization."""

    FLUTTER = "flutter"
    ADMIN_DASHBOARD = "admin_dashboard"
    CLOUD_FUNCTION = "cloud_function"
    WEB_VERSION = "web_version"
    DOCUMENTATION = "documentation"
    GENERAL = "general"
    DATA_TXT = "data_txt"
    LINK = "link"
    EXECUTE = "execute"

    @classmethod
    def display_name(cls, value: "ProjectType") -> str:
        """Human-readable display name for the type."""
        names = {
            ProjectType.FLUTTER: "Flutter",
            ProjectType.ADMIN_DASHBOARD: "Admin Dashboard",
            ProjectType.CLOUD_FUNCTION: "Cloud Function",
            ProjectType.WEB_VERSION: "Web Version",
            ProjectType.DOCUMENTATION: "Documentation",
            ProjectType.GENERAL: "General",
            ProjectType.DATA_TXT: "Data File (Notepad)",
            ProjectType.LINK: "Link",
            ProjectType.EXECUTE: "Execute / Open file",
        }
        return names.get(value, value.value)

    @classmethod
    def is_file_type(cls, value: "ProjectType") -> bool:
        """True if this type uses a file picker (not folder) for Browse."""
        return value in (ProjectType.DATA_TXT, ProjectType.EXECUTE)

    @classmethod
    def is_execute_type(cls, value: "ProjectType") -> bool:
        """True if Open should launch the file with the system default app."""
        return value == ProjectType.EXECUTE

    @classmethod
    def is_link_type(cls, value: "ProjectType") -> bool:
        """True if this type uses a URL input instead of folder picker."""
        return value == ProjectType.LINK

    @classmethod
    def icon_filename(cls, value: "ProjectType") -> str:
        """Icon filename for the type (e.g. flutter.png)."""
        return f"{value.value}.png"


@dataclass
class SubProjectCommand:
    """A terminal command saved on a sub-project, e.g. "npm run dev"."""

    command: str
    name: Optional[str] = None  # Label shown in the Run menu; if None, show the command
    run_on_open: bool = False  # Also run in a terminal when the sub-project is opened

    def display_name(self) -> str:
        """Label for the Run menu: custom name if set, else the command itself."""
        if self.name and self.name.strip():
            return self.name.strip()
        return self.command

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "run_on_open": self.run_on_open,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubProjectCommand":
        return cls(
            command=data.get("command", ""),
            name=data.get("name"),
            run_on_open=bool(data.get("run_on_open", False)),
        )


@dataclass
class SubProject:
    """A sub-project (directory) within a project."""

    id: str
    directory: str
    type: ProjectType
    name: Optional[str] = None  # Custom display name; if None, use folder/link
    commands: list[SubProjectCommand] = field(default_factory=list)

    def display_name(self) -> str:
        """Display name for sidebar: custom name if set, else folder name or link."""
        if self.name and self.name.strip():
            return self.name.strip()
        if self.type == ProjectType.LINK:
            return self.directory
        return Path(self.directory).name

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "directory": self.directory,
            "type": self.type.value,
            "name": self.name,
            "commands": [c.to_dict() for c in self.commands],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubProject":
        commands = [SubProjectCommand.from_dict(c) for c in data.get("commands", [])]
        if not commands and data.get("command"):
            # Older format: a single "command" + "run_on_open" on the sub-project
            commands = [SubProjectCommand(
                command=data["command"], run_on_open=bool(data.get("run_on_open", False))
            )]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            directory=data["directory"],
            type=ProjectType(data.get("type", "general")),
            name=data.get("name"),
            commands=commands,
        )


@dataclass
class Project:
    """A project containing multiple sub-projects."""

    id: str
    name: str
    icon_path: Optional[str] = None
    main_project_folder: Optional[str] = None
    sub_projects: list[SubProject] = field(default_factory=list)
    open_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "icon_path": self.icon_path,
            "main_project_folder": self.main_project_folder,
            "sub_projects": [sp.to_dict() for sp in self.sub_projects],
            "open_count": self.open_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            icon_path=data.get("icon_path"),
            main_project_folder=data.get("main_project_folder"),
            sub_projects=[
                SubProject.from_dict(sp) for sp in data.get("sub_projects", [])
            ],
            open_count=data.get("open_count", 0),
        )


@dataclass
class TextSnippet:
    """A saved text snippet for quick copy/paste."""

    id: str
    content: str

    def to_dict(self) -> dict:
        return {"id": self.id, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict) -> "TextSnippet":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data.get("content", ""),
        )
