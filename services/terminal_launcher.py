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


# Shell each terminal choice starts when no specific shell is requested
_DEFAULT_SHELL = {
    "windows_terminal": "powershell",
    "powershell": "powershell",
    "pwsh": "pwsh",
    "cmd": "cmd",
    "git_bash": "git_bash",
}


def _windows_command_line(shell: str, cwd: str, command: Optional[str]) -> Optional[str]:
    """Command line that starts shell interactively, running command first. None if not installed."""
    if shell == "cmd":
        # /S strips only the outer quotes, so the command is passed through unchanged
        return f'cmd.exe /S /K "{command}"' if command else "cmd.exe"
    if shell == "git_bash":
        bash = _find_git_bash()
        if not bash:
            return None
        # cd explicitly: Windows Terminal may start bash without our environment (CHERE_INVOKING)
        script = "cd " + shlex.quote(cwd.replace("\\", "/")) + "; "
        if command:
            script += f"{command}; "
        return subprocess.list2cmdline([bash, "--login", "-c", script + "exec bash -i"])
    if shell == "pwsh":
        pwsh = shutil.which("pwsh")
        return subprocess.list2cmdline(_powershell_args(pwsh, command)) if pwsh else None
    return subprocess.list2cmdline(_powershell_args("powershell.exe", command))


class TerminalLauncher:
    """Opens a folder in the chosen terminal, optionally running a command there."""

    def __init__(self, terminal: str = "windows_terminal"):
        """
        Args:
            terminal: One of the keys in TERMINALS.
        """
        self.terminal = terminal if terminal in TERMINALS else "windows_terminal"

    def open(self, path: str, command: Optional[str] = None, shell: Optional[str] = None) -> bool:
        """
        Open a terminal in the given folder (or a file's folder) and run command if given.
        The terminal stays open after the command finishes or is stopped.

        Args:
            shell: "powershell", "pwsh", "cmd" or "git_bash" to run command in that shell
                (e.g. VS Code tasks); default is the chosen terminal's own shell.

        Returns:
            True if launch was attempted successfully, False otherwise.
        """
        cwd = working_dir_for(path)
        if not cwd:
            return False
        command = (command or "").strip() or None
        try:
            if os.name == "nt":
                return self._open_windows(cwd, command, shell or _DEFAULT_SHELL[self.terminal])
            return self._open_posix(cwd, command)
        except Exception:
            return False

    def _open_windows(self, cwd: str, command: Optional[str], shell: str) -> bool:
        if shell == "pwsh" and not shutil.which("pwsh") and self.terminal != "pwsh":
            shell = "powershell"  # Only fail when PowerShell 7 was explicitly chosen
        command_line = _windows_command_line(shell, cwd, command)
        if not command_line:
            return False

        wt = shutil.which("wt") if self.terminal == "windows_terminal" else None
        if wt:
            # Windows Terminal treats ";" as its own command separator; "\;" passes it through
            wt_args = subprocess.list2cmdline([wt, "-d", cwd])
            subprocess.Popen(wt_args + " " + command_line.replace(";", "\\;"))
            return True

        # CHERE_INVOKING keeps a Git Bash login shell in cwd instead of jumping to HOME
        env = {**os.environ, "CHERE_INVOKING": "1"}
        subprocess.Popen(
            command_line, cwd=cwd, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE
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
