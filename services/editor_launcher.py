"""Launch Cursor, VS Code, Antigravity, Notepad, browser, or system default app for paths."""

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from models.project import ProjectType


def _quote_path(path: str) -> str:
    """Quote path for use in shell command on Windows."""
    return f'"{path}"'


def _get_antigravity_command() -> str:
    """
    Resolve Antigravity: GUI .exe on Windows, bundled CLI on macOS, or agy/antigravity on PATH.
    """
    if sys.platform == "darwin":
        bundle_cli = (
            Path("/Applications/Antigravity.app/Contents/Resources/app/bin/antigravity")
        )
        if bundle_cli.is_file():
            return str(bundle_cli)
        for name in ("agy", "antigravity"):
            found = shutil.which(name)
            if found:
                return found
        return "agy"

    if os.name == "nt":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        programfiles = os.environ.get("ProgramFiles", "")
        programfiles_x86 = os.environ.get("ProgramFiles(x86)", "")
        for exe in (
            Path(localappdata) / "Programs" / "Antigravity" / "Antigravity.exe",
            Path(localappdata) / "Google" / "Antigravity" / "Antigravity.exe",
            Path(programfiles) / "Google" / "Antigravity" / "Antigravity.exe",
            Path(programfiles_x86) / "Google" / "Antigravity" / "Antigravity.exe",
        ):
            if exe.is_file():
                return str(exe)
        bin_dir = Path(localappdata) / "Programs" / "Antigravity" / "resources" / "app" / "bin"
        for suffix in (".cmd", ".bat", ".exe"):
            candidate = bin_dir / f"antigravity{suffix}"
            if candidate.is_file():
                return str(candidate)
        for name in ("agy", "antigravity"):
            found = shutil.which(name)
            if found:
                return found
        return "agy"

    for name in ("agy", "antigravity"):
        found = shutil.which(name)
        if found:
            return found
    return "agy"


def _get_editor_exe(editor: str) -> str:
    """Get editor command; prefer full path on Windows when running as exe."""
    ed = (editor or "cursor").lower()
    if ed == "antigravity":
        return _get_antigravity_command()
    if os.name != "nt":
        return "cursor" if ed == "cursor" else "code"

    localappdata = os.environ.get("LOCALAPPDATA", "")
    programfiles = os.environ.get("ProgramFiles", "")

    if ed == "cursor":
        exe = Path(localappdata) / "Programs" / "cursor" / "Cursor.exe"
        if exe.exists():
            return str(exe)
        return "cursor"

    if ed == "code":
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
    """Opens project directories in Cursor, VS Code, or Antigravity."""

    def __init__(self, editor: str = "cursor"):
        """
        Args:
            editor: "cursor", "code" (VS Code), or "antigravity"
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

        if project_type == ProjectType.LINK:
            try:
                webbrowser.open(path)
                return True
            except Exception:
                return False

        if project_type == ProjectType.EXECUTE:
            if not os.path.isfile(path):
                return False
            try:
                if os.name == "nt":
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
                return True
            except Exception:
                return False

        if project_type == ProjectType.DATA_TXT:
            if not os.path.isfile(path):
                return False
            try:
                subprocess.Popen(f'notepad {_quote_path(path)}', shell=True)
                return True
            except Exception:
                return False

        # Flutter, Admin Dashboard, etc.: open file or folder in the chosen editor
        if not (os.path.isfile(path) or os.path.isdir(path)):
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
