"""Drop-down of a folder's launch configurations (.vscode/launch.json) and Flutter run."""

from typing import Optional

from PySide6.QtWidgets import QWidget

from services.project_service import ProjectService
from services.terminal_launcher import TerminalLauncher, _DEFAULT_SHELL
from services.vscode_launch import load_launch, LaunchConfig, LaunchError, LaunchFile, is_flutter_project, terminal_step
from services.vscode_tasks import (
    Step, TaskCancelled, TaskError, TaskResolver, build_script, load_tasks, task_shell,
)
from ui import dialogs
from ui.flutter_run_window import FlutterRunWindow
from ui.tasks_menu import ask_input
from ui.widgets import Menu


def has_launch_options(folder: str, launch: Optional[LaunchFile]) -> bool:
    return launch is not None or is_flutter_project(folder)


def quick_start(button: QWidget, folder: str, name: str = "", icon_path: Optional[str] = None) -> None:
    """Open the Flutter window and start the app with the device and settings saved for this folder."""
    FlutterRunWindow.open(button, folder, load_launch(folder), autorun=True, name=name, icon_path=icon_path)


def show_launch_menu(
    button: QWidget, folder: str, launch: Optional[LaunchFile], terminal: TerminalLauncher,
    name: str = "", icon_path: Optional[str] = None,
) -> None:
    """Pop up the configuration list under button; picking one runs it."""
    menu = Menu(button)
    if launch and launch.error:
        menu.add(launch.error, enabled=False)
    for config in (launch.configs if launch else []):
        if config.kind == "unsupported":
            menu.add(f"{config.name}  ·  {config.problem}", enabled=False)
        elif config.kind == "flutter":
            menu.add(
                f"{config.name}   (Flutter)",
                lambda _=False, c=config: FlutterRunWindow.open(
                    button, folder, launch, c.name, name=name, icon_path=icon_path),
                icon_name="play",
            )
        else:
            menu.add(config.name, lambda _=False, c=config: run_in_terminal(button, folder, c, terminal), icon_name="terminal")
    if launch and not launch.error and not launch.configs:
        menu.add("No configurations in launch.json", enabled=False)

    if is_flutter_project(folder):
        if menu.actions():
            menu.addSeparator()
        menu.add(
            "Flutter run…",
            lambda: FlutterRunWindow.open(button, folder, launch, name=name, icon_path=icon_path),
            icon_name="launch",
        )
    menu.popup_below(button)


def run_in_terminal(parent: QWidget, folder: str, config: LaunchConfig, terminal: TerminalLauncher) -> None:
    """Run a node/python/Dart configuration in a terminal, after its preLaunchTask if it has one."""
    shell = _DEFAULT_SHELL[terminal.terminal]
    try:
        steps: list[Step] = []
        pre_task = config.data.get("preLaunchTask")
        if pre_task:
            tasks_file = load_tasks(folder)
            task = tasks_file.find(str(pre_task)) if tasks_file else None
            if task is None:
                raise TaskError(f'preLaunchTask "{pre_task}" was not found in tasks.json.')
            shell = task_shell(tasks_file, task, ProjectService.get_editor())
            launches = TaskResolver(tasks_file, shell, lambda spec: ask_input(parent, spec)).resolve(task)
            steps = [step for launch in launches for step in launch]
        steps.append(terminal_step(folder, config, shell))
    except TaskCancelled:
        return
    except (LaunchError, TaskError) as e:
        dialogs.error(parent.window(), "VS Code launch", str(e))
        return

    cwd, script = build_script(steps, shell)
    if not terminal.open(cwd, script, shell=shell):
        dialogs.error(
            parent.window(), "VS Code launch",
            f'Could not run "{config.name}" in:\n{cwd}\n\n'
            "Check that the folder exists and the terminal is installed.",
        )
