"""Open folders in a terminal (Windows Terminal, PowerShell, CMD, Git Bash) and optionally run a command."""

import base64
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Terminal key -> display name (keys are stored in settings.json)
TERMINALS = {
    "windows_terminal": "Windows Terminal",
    "powershell": "PowerShell",
    "pwsh": "PowerShell 7",
    "cmd": "Command Prompt",
    "git_bash": "Git Bash",
}


def working_dir_for(path: str) -> Optional[str]:
    """Folder to open the terminal in: the path itself, or a file's parent folder."""
    if not path:
        return None
    if os.path.isdir(path):
        return path
    if os.path.isfile(path):
        return str(Path(path).parent)
    return None


def _encode_powershell(command: str) -> str:
    """Encode a command for -EncodedCommand so quotes and semicolons survive intact."""
    return base64.b64encode(command.encode("utf-16-le")).decode("ascii")


def _powershell_args(exe: str, command: Optional[str]) -> list[str]:
    args = [exe, "-NoExit", "-NoLogo"]
    if command:
        args += ["-EncodedCommand", _encode_powershell(command)]
    return args


def _find_git_bash() -> Optional[str]:
    """Locate Git for Windows' bash.exe."""
    for base in (
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"),
    ):
        if base:
            exe = Path(base) / "Git" / "bin" / "bash.exe"
            if exe.is_file():
                return str(exe)
    git = shutil.which("git")
    if git:
        exe = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if exe.is_file():
            return str(exe)
    return None


class TerminalLauncher:
    """Opens a folder in the chosen terminal, optionally running a command there."""

    def __init__(self, terminal: str = "windows_terminal"):
        """
        Args:
            terminal: One of the keys in TERMINALS.
        """
        self.terminal = terminal if terminal in TERMINALS else "windows_terminal"

    def open(self, path: str, command: Optional[str] = None) -> bool:
        """
        Open a terminal in the given folder (or a file's folder) and run command if given.
        The terminal stays open after the command finishes or is stopped.

        Returns:
            True if launch was attempted successfully, False otherwise.
        """
        cwd = working_dir_for(path)
        if not cwd:
            return False
        command = (command or "").strip() or None
        try:
            if os.name == "nt":
                return self._open_windows(cwd, command)
            return self._open_posix(cwd, command)
        except Exception:
            return False

    def _open_windows(self, cwd: str, command: Optional[str]) -> bool:
        new_console = subprocess.CREATE_NEW_CONSOLE
        term = self.terminal

        if term == "windows_terminal":
            wt = shutil.which("wt")
            if wt:
                subprocess.Popen([wt, "-d", cwd] + _powershell_args("powershell.exe", command))
                return True
            term = "powershell"  # Windows Terminal not installed

        if term == "pwsh":
            pwsh = shutil.which("pwsh")
            if not pwsh:
                return False
            subprocess.Popen(_powershell_args(pwsh, command), cwd=cwd, creationflags=new_console)
            return True

        if term == "cmd":
            # /S strips only the outer quotes, so the command is passed through unchanged
            args = f'cmd.exe /S /K "{command}"' if command else "cmd.exe"
            subprocess.Popen(args, cwd=cwd, creationflags=new_console)
            return True

        if term == "git_bash":
            bash = _find_git_bash()
            if not bash:
                return False
            args = [bash, "--login", "-i"]
            if command:
                args = [bash, "--login", "-c", f"{command}; exec bash -i"]
            # CHERE_INVOKING keeps the login shell in cwd instead of jumping to HOME
            env = {**os.environ, "CHERE_INVOKING": "1"}
            subprocess.Popen(args, cwd=cwd, env=env, creationflags=new_console)
            return True

        subprocess.Popen(
            _powershell_args("powershell.exe", command), cwd=cwd, creationflags=new_console
        )
        return True

    def _open_posix(self, cwd: str, command: Optional[str]) -> bool:
        if sys.platform == "darwin":
            if not command:
                subprocess.Popen(["open", "-a", "Terminal", cwd])
                return True
            script = f"cd {shlex.quote(cwd)} && {command}"
            script = script.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen(
                ["osascript", "-e", f'tell application "Terminal" to do script "{script}"']
            )
            return True

        term = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal")
        if not term:
            return False
        args = [term]
        if command:
            args += ["-e", "bash", "-c", f"{command}; exec bash"]
        subprocess.Popen(args, cwd=cwd)
        return True
