"""Data models for Project and SubProject."""

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
            ProjectType.DATA_TXT: "Data File (txt)",
            ProjectType.LINK: "Link",
        }
        return names.get(value, value.value)

    @classmethod
    def is_file_type(cls, value: "ProjectType") -> bool:
        """True if this type uses a file picker instead of folder picker."""
        return value == ProjectType.DATA_TXT

    @classmethod
    def is_link_type(cls, value: "ProjectType") -> bool:
        """True if this type uses a URL input instead of folder picker."""
        return value == ProjectType.LINK

    @classmethod
    def icon_filename(cls, value: "ProjectType") -> str:
        """Icon filename for the type (e.g. flutter.png)."""
        return f"{value.value}.png"


@dataclass
class SubProject:
    """A sub-project (directory) within a project."""

    id: str
    directory: str
    type: ProjectType
    name: Optional[str] = None  # Custom display name; if None, use folder/link

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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubProject":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            directory=data["directory"],
            type=ProjectType(data.get("type", "general")),
            name=data.get("name"),
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
