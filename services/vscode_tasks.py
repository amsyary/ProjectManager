"""Read .vscode/tasks.json and turn tasks into shell scripts that run outside VS Code."""

import json
import os
import re
import shlex
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_VAR = re.compile(r"\$\{([^}]+)\}")


class TaskError(Exception):
    """The task can't run outside VS Code (unknown type, VS Code-only variable, ...)."""


class TaskCancelled(Exception):
    """The user cancelled an ${input:...} prompt."""


def parse_jsonc(text: str):
    """Parse JSON with comments and trailing commas, as VS Code allows."""
    out: list[str] = []
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        elif c in "}]":
            k = len(out) - 1
            while k >= 0 and out[k].isspace():
                k -= 1
            if k >= 0 and out[k] == ",":
                del out[k]
        out.append(c)
        i += 1
    return json.loads("".join(out))


def _merge_options(base: dict, override: dict) -> dict:
    """Task options override file-level options; env is merged key by key."""
    merged = {**base, **override}
    if "env" in base or "env" in override:
        merged["env"] = {**base.get("env", {}), **override.get("env", {})}
    return merged


@dataclass
class VSCodeTask:
    label: str
    data: dict  # Raw task with the "windows" overrides applied on Windows
    hidden: bool = False
    detail: Optional[str] = None


@dataclass
class TasksFile:
    folder: str
    tasks: list[VSCodeTask] = field(default_factory=list)
    inputs: dict[str, dict] = field(default_factory=dict)
    options: dict = field(default_factory=dict)  # File-level options (cwd, env, shell)
    error: Optional[str] = None

    def visible_tasks(self) -> list[VSCodeTask]:
        """Tasks shown in the menu ("hide": true tasks only run as dependencies)."""
        return [t for t in self.tasks if not t.hidden]

    def find(self, ref) -> Optional[VSCodeTask]:
        """Find a dependsOn target: a label, or {"task": label} / {"type": "npm", "script": ...}."""
        if isinstance(ref, dict):
            if "task" in ref:
                ref = ref["task"]
            else:
                return next(
                    (t for t in self.tasks if all(t.data.get(k) == v for k, v in ref.items())),
                    None,
                )
        return next((t for t in self.tasks if t.label == ref), None)


def load_tasks(folder: str) -> Optional[TasksFile]:
    """Read <folder>/.vscode/tasks.json. None if there isn't one; .error is set if it's invalid."""
    if not folder or not os.path.isdir(folder):
        return None
    path = Path(folder) / ".vscode" / "tasks.json"
    if not path.is_file():
        return None
    result = TasksFile(folder=folder)
    try:
        data = parse_jsonc(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        result.error = f"tasks.json could not be read: {e}"
        return result
    if not isinstance(data, dict):
        result.error = "tasks.json has no tasks"
        return result

    platform_key = "windows" if os.name == "nt" else ("osx" if sys.platform == "darwin" else "linux")
    result.options = data.get("options", {})
    platform_top = data.get(platform_key, {})
    if isinstance(platform_top, dict):
        result.options = _merge_options(result.options, platform_top.get("options", {}))
    result.inputs = {i["id"]: i for i in data.get("inputs", []) if isinstance(i, dict) and "id" in i}

    for raw in data.get("tasks", []):
        if not isinstance(raw, dict):
            continue
        task = dict(raw)
        override = raw.get(platform_key)
        if isinstance(override, dict):
            task.update({k: v for k, v in override.items() if k != "options"})
            if "options" in override:
                task["options"] = _merge_options(raw.get("options", {}), override["options"])
        label = task.get("label") or task.get("taskName") or task.get("script")
        if not label:
            continue
        result.tasks.append(VSCodeTask(
            label=str(label), data=task, hidden=bool(task.get("hide")), detail=task.get("detail"),
        ))
    return result


# --- Which shell VS Code would run a task in -------------------------------------------------

_EDITOR_SETTINGS_DIR = {"cursor": "Cursor", "code": "Code", "antigravity": "Antigravity"}


def _shell_from_executable(executable: str) -> Optional[str]:
    name = Path(executable).name.lower()
    if name.startswith("cmd"):
        return "cmd"
    if name.startswith("pwsh"):
        return "pwsh"
    if name.startswith("powershell"):
        return "powershell"
    if "bash" in name:
        return "git_bash"
    return None


def _editor_default_shell(editor: str) -> Optional[str]:
    """The shell the editor's terminal settings use for tasks on Windows, if configured."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    path = Path(appdata) / _EDITOR_SETTINGS_DIR.get(editor, "Code") / "User" / "settings.json"
    try:
        settings = parse_jsonc(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None

    automation = settings.get("terminal.integrated.automationProfile.windows")
    if isinstance(automation, dict) and automation.get("path"):
        return _shell_from_executable(automation["path"])

    profile_name = settings.get("terminal.integrated.defaultProfile.windows")
    if not profile_name:
        return None
    profile = settings.get("terminal.integrated.profiles.windows", {}).get(profile_name, {})
    paths = profile.get("path") if isinstance(profile, dict) else None
    if isinstance(paths, list):
        paths = paths[0] if paths else None
    if paths:
        return _shell_from_executable(paths)
    source = (profile.get("source") if isinstance(profile, dict) else None) or profile_name
    if source == "Command Prompt":
        return "cmd"
    if source == "Git Bash":
        return "git_bash"
    if source == "PowerShell":
        return "pwsh" if shutil.which("pwsh") else "powershell"
    return None


def task_shell(tasks_file: TasksFile, task: VSCodeTask, editor: str) -> str:
    """Shell for a task: its options.shell, then the editor's terminal profile, then VS Code's default."""
    if os.name != "nt":
        return "git_bash"  # bash syntax
    options = _merge_options(tasks_file.options, task.data.get("options", {}))
    shell = options.get("shell")
    if isinstance(shell, dict) and shell.get("executable"):
        found = _shell_from_executable(shell["executable"])
        if found:
            return found
    return _editor_default_shell(editor) or ("pwsh" if shutil.which("pwsh") else "powershell")


# --- Turning a task (and its dependsOn) into scripts -----------------------------------------

def quote_arg(s: str, shell: str) -> str:
    """Quote like VS Code: only when the value contains whitespace (or is empty)."""
    if s and not any(ch.isspace() for ch in s):
        return s
    if shell == "cmd":
        return f'"{s}"'
    if shell == "git_bash":
        return shlex.quote(s)
    return "'" + s.replace("'", "''") + "'"


@dataclass
class Step:
    label: str  # Task the step came from
    cwd: str
    env: dict
    command: str


AskInput = Callable[[dict], Optional[str]]  # Gets an "inputs" entry, returns the value or None


class TaskResolver:
    """Resolves a task into launches: each launch is a list of steps run in one terminal."""

    def __init__(self, tasks_file: TasksFile, shell: str, ask_input: AskInput):
        self._file = tasks_file
        self._shell = shell
        self._ask_input = ask_input
        self._answers: dict[str, str] = {}  # Each ${input:id} is asked once per run

    def resolve(self, task: VSCodeTask) -> list[list[Step]]:
        # A task reached through several dependsOn paths runs once, like in VS Code
        seen: set[str] = set()
        launches = []
        for launch in self._resolve(task, []):
            steps = []
            for step in launch:
                if step.label not in seen:
                    seen.add(step.label)
                    steps.append(step)
            if steps:
                launches.append(steps)
        if not launches:
            raise TaskError(f'"{task.label}" has nothing to run.')
        return launches

    def _resolve(self, task: VSCodeTask, stack: list[str]) -> list[list[Step]]:
        if task.label in stack:
            raise TaskError(f'Circular dependsOn: "{task.label}"')
        stack = stack + [task.label]

        refs = task.data.get("dependsOn") or []
        if not isinstance(refs, list):
            refs = [refs]
        deps = []
        for ref in refs:
            dep = self._file.find(ref)
            if dep is None:
                raise TaskError(f'"{task.label}" depends on a task that was not found: {ref}')
            deps.append(dep)

        own = self._own_step(task)
        dep_launches = [self._resolve(d, stack) for d in deps]

        if task.data.get("dependsOrder") == "sequence":
            steps = [s for launches in dep_launches for launch in launches for s in launch]
            if own:
                steps.append(own)
            return [steps] if steps else []

        # Parallel (VS Code's default): a task with only dependsOn opens each dependency in its own
        # terminal. Otherwise dependencies run before the task, except background ones (watch/serve).
        separate: list[list[Step]] = []
        before: list[Step] = []
        for dep, launches in zip(deps, dep_launches):
            if own is None or dep.data.get("isBackground"):
                separate += launches
            else:
                before += [s for launch in launches for s in launch]
        if own:
            separate.append(before + [own])
        return separate

    def _own_step(self, task: VSCodeTask) -> Optional[Step]:
        t = task.data
        task_type = t.get("type", "process")
        options = _merge_options(self._file.options, t.get("options", {}))
        cwd = self._sub(options["cwd"]) if options.get("cwd") else self._file.folder
        env = {k: self._sub(str(v)) for k, v in options.get("env", {}).items()}

        if task_type == "npm":
            script = t.get("script")
            if not script:
                raise TaskError(f'npm task "{task.label}" has no script.')
            if t.get("path") and not options.get("cwd"):
                cwd = os.path.join(self._file.folder, t["path"])
            command = "npm install" if script == "install" else f"npm run {self._quote(script)}"
        elif task_type == "typescript":
            tsconfig = t.get("tsconfig", "tsconfig.json")
            watch = "-w " if t.get("option") == "watch" else ""
            command = f"npx tsc {watch}-p {self._quote(tsconfig)}"
        elif "command" in t:
            command = self._command_line(t["command"], t.get("args", []))
        elif t.get("dependsOn"):
            return None
        else:
            raise TaskError(f'"{task_type}" tasks only run inside VS Code.')
        return Step(label=task.label, cwd=self._path(cwd), env=env, command=command)

    def _command_line(self, command, args: list) -> str:
        command = self._sub(self._value(command))
        if not args:
            return command
        line = " ".join([self._quote(command)] + [self._quote(self._sub(self._value(a))) for a in args])
        if self._shell in ("powershell", "pwsh") and line.startswith("'"):
            line = "& " + line  # PowerShell needs & to run a quoted executable path
        return line

    @staticmethod
    def _value(item) -> str:
        """Args may be {"value": ..., "quoting": ...} objects."""
        return str(item.get("value", "")) if isinstance(item, dict) else str(item)

    def _quote(self, s: str) -> str:
        return quote_arg(s, self._shell)

    def _path(self, p) -> str:
        p = os.path.normpath(str(p))
        return p.replace("\\", "/") if self._shell == "git_bash" else p

    def _sub(self, s: str) -> str:
        """Replace ${...} variables the way VS Code does."""
        def repl(m: re.Match) -> str:
            name = m.group(1)
            if name in ("workspaceFolder", "workspaceRoot", "cwd"):
                return self._path(self._file.folder)
            if name == "workspaceFolderBasename":
                return Path(self._file.folder).name
            if name == "userHome":
                return self._path(Path.home())
            if name in ("pathSeparator", "/"):
                return "/" if self._shell == "git_bash" else os.sep
            if name.startswith("env:"):
                return os.environ.get(name[4:], "")
            if name.startswith("input:"):
                return self._input(name[6:])
            raise TaskError(f"${{{name}}} only works inside VS Code.")
        return _VAR.sub(repl, s)

    def _input(self, input_id: str) -> str:
        if input_id in self._answers:
            return self._answers[input_id]
        spec = self._file.inputs.get(input_id)
        if spec is None:
            raise TaskError(f"Input \"{input_id}\" is not defined in tasks.json.")
        if spec.get("type") not in ("promptString", "pickString"):
            raise TaskError(f"Input \"{input_id}\" ({spec.get('type')}) only works inside VS Code.")
        value = self._ask_input(spec)
        if value is None:
            raise TaskCancelled()
        self._answers[input_id] = value
        return value


def check_task(tasks_file: TasksFile, task: VSCodeTask) -> Optional[str]:
    """Why the task can't run outside VS Code, or None if it can (inputs are not asked)."""
    try:
        TaskResolver(tasks_file, "cmd", lambda spec: "").resolve(task)
    except TaskError as e:
        return str(e)
    return None


def build_script(launch: list[Step], shell: str) -> tuple[str, str]:
    """(cwd, script) for one terminal: steps run in order and stop at the first failure."""
    cwd = launch[0].cwd
    parts: list[str] = []
    current = cwd
    for step in launch:
        if step.cwd != current:
            parts.append(_cd(step.cwd, shell))
            current = step.cwd
        parts += [_set_env(k, v, shell) for k, v in step.env.items()]
        parts.append(step.command)
    return cwd, _and_then(parts, shell)


def _cd(path: str, shell: str) -> str:
    if shell == "cmd":
        return f'cd /d "{path}"'
    if shell == "git_bash":
        return f"cd {shlex.quote(path)}"
    return "Set-Location -LiteralPath '" + path.replace("'", "''") + "'"


def _set_env(key: str, value: str, shell: str) -> str:
    if shell == "cmd":
        return f'set "{key}={value}"'
    if shell == "git_bash":
        return f"export {key}={shlex.quote(value)}"
    return f"$env:{key} = '" + value.replace("'", "''") + "'"


def _and_then(parts: list[str], shell: str) -> str:
    if shell in ("powershell", "pwsh"):
        # Windows PowerShell 5.1 has no &&
        script = parts[-1]
        for part in reversed(parts[:-1]):
            script = f"{part}; if ($?) {{ {script} }}"
        return script
    return " && ".join(parts)
