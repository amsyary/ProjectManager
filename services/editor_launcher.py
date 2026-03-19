"""Launch Cursor, VS Code, Notepad, or browser for project paths."""

import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

from models.project import ProjectType


def _quote_path(path: str) -> str:
    """Quote path for use in shell command on Windows."""
    return f'"{path}"'


def _get_editor_exe(editor: str) -> str:
    """Get editor command; prefer full path on Windows when running as exe."""
    if os.name != "nt":
        return "cursor" if editor == "cursor" else "code"

    localappdata = os.environ.get("LOCALAPPDATA", "")
    programfiles = os.environ.get("ProgramFiles", "")

    if editor == "cursor":
        exe = Path(localappdata) / "Programs" / "cursor" / "Cursor.exe"
        if exe.exists():
            return str(exe)
        return "cursor"

    if editor == "code":
        for base in [programfiles, localappdata]:
            exe = Path(base) / "Microsoft VS Code" / "Code.exe"
            if exe.exists():
                return str(exe)
        exe = Path(localappdata) / "Programs" / "Microsoft VS Code" / "Code.exe"
        if exe.exists():
            return str(exe)
        return "code"

    return "cursor"


class EditorLauncher:
    """Opens project directories in Cursor or VS Code."""

    def __init__(self, editor: str = "cursor"):
        """
        Args:
            editor: "cursor" or "code" (VS Code)
        """
        self.editor = editor.lower() if editor else "cursor"

    def _get_editor_command(self) -> str:
        """Get the editor command for launching."""
        return _get_editor_exe(self.editor)

    def open(self, path: str, project_type: Optional[ProjectType] = None) -> bool:
        """
        Open the given path in the appropriate application.

        Args:
            path: Absolute path to the project directory or file.
            project_type: Optional type; for DATA_TXT opens in Notepad.

        Returns:
            True if launch was attempted successfully, False otherwise.
        """
        if not path:
            return False

        if project_type == ProjectType.DATA_TXT:
            if not os.path.isfile(path):
                return False
            try:
                subprocess.Popen(f'notepad {_quote_path(path)}', shell=True)
                return True
            except Exception:
                return False

        if project_type == ProjectType.LINK:
            try:
                webbrowser.open(path)
                return True
            except Exception:
                return False

        if not os.path.isdir(path):
            return False

        cmd = self._get_editor_command()
        quoted_path = _quote_path(path)
        if os.path.isfile(cmd):
            full_cmd = f"{_quote_path(cmd)} {quoted_path}"
        else:
            full_cmd = f"{cmd} {quoted_path}"
        try:
            subprocess.Popen(full_cmd, shell=True)
            return True
        except Exception:
            return False

    def open_in_explorer(self, path: str) -> bool:
        """
        Open the given folder in Windows Explorer (file browser).

        Args:
            path: Absolute path to the folder.

        Returns:
            True if launch was attempted successfully, False otherwise.
        """
        if not path or not os.path.isdir(path):
            return False
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            return False
