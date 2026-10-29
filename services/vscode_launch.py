"""Read .vscode/launch.json and turn configurations into Flutter run settings or terminal commands."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.vscode_tasks import Step, parse_jsonc, quote_arg

_VAR = re.compile(r"\$\{([^}]+)\}")
_FLUTTER_SDK = re.compile(r"^\s*sdk:\s*flutter\s*$", re.MULTILINE)

FLUTTER_MODES = ("debug", "profile", "release")


class LaunchError(Exception):
    """The configuration can't run outside VS Code (unknown type, VS Code-only variable, ...)."""


@dataclass
class FlutterRunSettings:
    """Everything `flutter run` needs; also what the Flutter window's fields edit."""

    cwd: str
    target: str = "lib/main.dart"
    mode: str = "debug"
    device_id: Optional[str] = None
    flavor: str = ""
    tool_args: list[str] = field(default_factory=list)  # Extra `flutter run` arguments
    app_args: list[str] = field(default_factory=list)  # Passed to the Dart app
    env: dict = field(default_factory=dict)


@dataclass
class LaunchConfig:
    name: str
    data: dict
    kind: str  # "flutter" | "terminal" | "unsupported"
    problem: Optional[str] = None  # Why it is "unsupported"


@dataclass
class LaunchFile:
    folder: str
    configs: list[LaunchConfig] = field(default_factory=list)
    error: Optional[str] = None


def is_flutter_project(folder: str) -> bool:
    """True if folder has a pubspec.yaml that depends on the Flutter SDK."""
    try:
        text = (Path(folder) / "pubspec.yaml").read_text(encoding="utf-8-sig")
    except OSError:
        return False
    return bool(_FLUTTER_SDK.search(text))


def load_launch(folder: str) -> Optional[LaunchFile]:
    """Read <folder>/.vscode/launch.json. None if there isn't one; .error is set if it's invalid."""
    if not folder or not os.path.isdir(folder):
        return None
    path = Path(folder) / ".vscode" / "launch.json"
    if not path.is_file():
        return None
    result = LaunchFile(folder=folder)
    try:
        data = parse_jsonc(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        result.error = f"launch.json could not be read: {e}"
        return result
    if not isinstance(data, dict):
        result.error = "launch.json has no configurations"
        return result

    for raw in data.get("configurations", []):
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        kind, problem = _classify(folder, raw)
        result.configs.append(LaunchConfig(name=str(raw["name"]), data=raw, kind=kind, problem=problem))
    return result


def _classify(folder: str, raw: dict) -> tuple[str, Optional[str]]:
    config_type = raw.get("type")
    if raw.get("request", "launch") != "launch":
        return "unsupported", f'"{raw.get("request")}" configurations only work inside VS Code'
    if config_type == "dart":
        try:
            cwd = _config_cwd(folder, raw)
        except LaunchError as e:
            return "unsupported", str(e)
        return ("flutter" if is_flutter_project(cwd) else "terminal"), None
    if config_type in ("node", "pwa-node"):
        if not (raw.get("program") or raw.get("runtimeExecutable")):
            return "unsupported", "no program or runtimeExecutable"
        return "terminal", None
    if config_type in ("python", "debugpy"):
        if not (raw.get("program") or raw.get("module")):
            return "unsupported", "no program or module"
        return "terminal", None
    return "unsupported", f'"{config_type}" configurations only work inside VS Code'


def _sub(s: str, folder: str) -> str:
    """Replace ${...} variables the way VS Code does."""
    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name in ("workspaceFolder", "workspaceRoot", "cwd"):
            return folder
        if name == "workspaceFolderBasename":
            return Path(folder).name
        if name == "userHome":
            return str(Path.home())
        if name in ("pathSeparator", "/"):
            return os.sep
        if name.startswith("env:"):
            return os.environ.get(name[4:], "")
        raise LaunchError(f"${{{name}}} only works inside VS Code.")
    return _VAR.sub(repl, s)


def _config_cwd(folder: str, raw: dict) -> str:
    cwd = raw.get("cwd")
    if not cwd:
        return folder
    return os.path.normpath(os.path.join(folder, _sub(str(cwd), folder)))


def _strings(values, folder: str) -> list[str]:
    return [_sub(str(v), folder) for v in (values or [])]


def flutter_settings(folder: str, config: LaunchConfig) -> FlutterRunSettings:
    """Run settings for a "flutter" configuration (dart + flutterMode/deviceId/program/toolArgs...)."""
    raw = config.data
    mode = raw.get("flutterMode", "debug")
    program = _sub(str(raw.get("program") or "lib/main.dart"), folder)
    cwd = _config_cwd(folder, raw)
    if os.path.isabs(program):
        try:
            program = os.path.relpath(program, cwd)
        except ValueError:
            pass  # Different drive: keep it absolute
    device = raw.get("deviceId")
    return FlutterRunSettings(
        cwd=cwd,
        target=program.replace("\\", "/"),
        mode=mode if mode in FLUTTER_MODES else "debug",
        device_id=_sub(str(device), folder) if device else None,
        # launch.json "args" are flutter run arguments in practice (--flavor, --dart-define, ...)
        tool_args=_strings(raw.get("toolArgs"), folder) + _strings(raw.get("args"), folder),
        env={k: _sub(str(v), folder) for k, v in (raw.get("env") or {}).items()},
    )


def terminal_step(folder: str, config: LaunchConfig, shell: str) -> Step:
    """The command a "terminal" configuration runs (node, python, plain Dart)."""
    raw = config.data
    cwd = _config_cwd(folder, raw)
    env = {k: _sub(str(v), folder) for k, v in (raw.get("env") or {}).items()}
    args = _strings(raw.get("args"), folder)

    config_type = raw.get("type")
    if config_type == "dart":
        program = _sub(str(raw.get("program") or "lib/main.dart"), folder)
        parts = ["dart", "run", *_strings(raw.get("toolArgs"), folder), program, *args]
    elif config_type in ("node", "pwa-node"):
        exe = _sub(str(raw.get("runtimeExecutable") or "node"), folder)
        program = [_sub(str(raw["program"]), folder)] if raw.get("program") else []
        parts = [exe, *_strings(raw.get("runtimeArgs"), folder), *program, *args]
    else:  # python / debugpy
        exe = _sub(str(raw.get("python") or "python"), folder)
        if raw.get("module"):
            target = ["-m", _sub(str(raw["module"]), folder)]
        else:
            target = [_sub(str(raw["program"]), folder)]
        parts = [exe, *_strings(raw.get("pythonArgs"), folder), *target, *args]

    command = " ".join(quote_arg(p, shell) for p in parts)
    if shell in ("powershell", "pwsh") and command.startswith("'"):
        command = "& " + command  # PowerShell needs & to run a quoted executable path
    return Step(label=config.name, cwd=cwd, env=env, command=command)
