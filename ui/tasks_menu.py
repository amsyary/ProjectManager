"""Drop-down menu of a folder's VS Code tasks (.vscode/tasks.json) that runs them in a terminal."""

from typing import Optional

from PySide6.QtWidgets import QWidget

from services.project_service import ProjectService
from services.terminal_launcher import TerminalLauncher
from services.vscode_tasks import (
    TasksFile, VSCodeTask, TaskResolver, TaskError, TaskCancelled,
    check_task, build_script, task_shell,
)
from ui import dialogs
from ui.widgets import Menu


def show_tasks_menu(button: QWidget, tasks_file: TasksFile, terminal: TerminalLauncher) -> None:
    """Pop up the task list under button; picking a task runs it."""
    menu = Menu(button)
    if tasks_file.error:
        menu.add(tasks_file.error, enabled=False)
    for task in tasks_file.visible_tasks():
        problem = check_task(tasks_file, task)
        if problem:
            menu.add(f"{task.label}  ·  {problem}", enabled=False)
        else:
            menu.add(
                task.label, lambda _=False, t=task: run_task(button, tasks_file, t, terminal),
                icon_name="tasks", tip=task.detail or "",
            )
    if not tasks_file.error and not tasks_file.visible_tasks():
        menu.add("No tasks in tasks.json", enabled=False)
    menu.popup_below(button)


def run_task(parent: QWidget, tasks_file: TasksFile, task: VSCodeTask, terminal: TerminalLauncher) -> None:
    """Ask for any ${input:...} values, then open one terminal per launch."""
    shell = task_shell(tasks_file, task, ProjectService.get_editor())
    try:
        launches = TaskResolver(tasks_file, shell, lambda spec: ask_input(parent, spec)).resolve(task)
    except TaskCancelled:
        return
    except TaskError as e:
        dialogs.error(parent.window(), "VS Code task", str(e))
        return
    for launch in launches:
        cwd, script = build_script(launch, shell)
        if not terminal.open(cwd, script, shell=shell):
            dialogs.error(
                parent.window(), "VS Code task",
                f'Could not run "{task.label}" in:\n{cwd}\n\n'
                "Check that the folder exists and the terminal is installed.",
            )
            return


def ask_input(parent: QWidget, spec: dict) -> Optional[str]:
    """Show a promptString or pickString input from tasks.json. None if cancelled."""
    title = spec.get("id", "Input")
    description = spec.get("description") or title
    window = parent.window()
    if spec.get("type") == "pickString":
        values, labels = [], []
        for opt in spec.get("options", []):
            if isinstance(opt, dict):
                value = str(opt.get("value", ""))
                labels.append(str(opt.get("label") or value))
            else:
                value = str(opt)
                labels.append(value)
            values.append(value)
        return dialogs.ask_pick(window, title, description, labels, values, spec.get("default"))
    return dialogs.ask_text(
        window, title, description, initial=str(spec.get("default", "")),
        password=bool(spec.get("password")), ok_text="Run",
    )
