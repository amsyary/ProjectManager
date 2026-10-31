# Product

<!-- impeccable:product-schema 1 -->

## Platform

Native Windows desktop app (Python 3.12, PySide6 / Qt Widgets), packaged as a one-file exe with PyInstaller. Not a web surface.

## Users

One developer (the author) who juggles many client projects on Windows. A typical project is several folders: a Flutter app, an admin dashboard, cloud functions, a web build, docs, plus loose files (keys, .env) and links. They open Project Manager as a **quick launcher**: find a project, fire off the editor / terminal / Flutter run / VS Code task they need in a few clicks, then go back to work.

## Product Purpose

Replace "navigate folders, remember paths, open five windows by hand" with one click per action. Success means getting from the app opening to the right thing running in seconds, without reaching for the mouse more than needed.

## Positioning

A launcher that understands a project as a *bundle of folders* and knows what each folder can do: open in Cursor / VS Code / Antigravity / Claude Desktop, terminal in the user's preferred shell, saved per-folder commands, `.vscode/tasks.json` tasks, `.vscode/launch.json` configurations, and a full Flutter run console (device, mode, flavor, hot reload/restart, service-extension toggles) without opening VS Code.

## Operating Context

- Lives beside the editor on a Windows desktop; opened many times a day, mostly briefly.
- Flutter run windows and scrcpy mirroring can stay open for long sessions.
- Tools on PATH it shells out to: cursor/code/antigravity, wt/powershell/pwsh/cmd/git-bash, flutter, adb, scrcpy, notepad.

## Capabilities and Constraints

Every existing capability must keep working:

- Projects: name, icon (file or `default_icon:` bundled icon), optional main folder, sub-projects; add / edit / delete; search by name; sorted by most opened (`open_count`).
- Sub-project types: Flutter, Admin Dashboard, Cloud Function, Web Version, Documentation, General, Data File (opens in Notepad), Execute / Open file (system default app), Link (browser).
- Per sub-project: Open, Terminal, saved Commands (Run / Run menu / Run all / run-on-open), VS Code Tasks menu (with `${input:}` prompts: promptString and pickString), Launch menu (launch.json + "Flutter run..."), Flutter quick-start.
- Project level: open main folder in Explorer, Terminal, Tasks, Launch for the main folder, Open All.
- Flutter run window per folder: configuration, device list (refresh), mode, target, flavor (auto-detected), extra args, Run / Stop / Hot Reload (Ctrl+R) / Hot Restart (Ctrl+Shift+R), 9 service-extension toggles, live log, remembers settings per folder, quick-start autorun, stops flutter on app close.
- scrcpy: device picker, run on all, failure reporting.
- Text snippets: add, edit, delete, copy.
- Settings: editor, terminal, theme (dark/light). Export / Import (overwrite or merge) projects as JSON.
- Data compatibility: `data/projects.json` and `config/settings.json` formats stay unchanged; the exe keeps its own data beside it.
- Build: PyInstaller one-file windowed exe via `ProjectManager.spec`; Python launched with `py` (3.12).

## Brand Commitments

Name: "Project Manager" (window title must stay "Project Manager"; smoke tests look for it). Bundled type icons in `assets/icons/` and user-chosen project icons are real content and must display.

## Evidence on Hand

- Type icons: `assets/icons/*.png`; default project icons: `assets/icons/default_icon/`.
- Real user data shape: `data/projects.json`.

## Product Principles

1. Launch speed beats decoration: the next action is always one click or one keystroke away.
2. Every folder shows only the actions it can actually perform (tasks/launch/Flutter appear when detected).
3. Never lose user data: formats stay compatible, destructive actions confirm.
4. Long-running things (Flutter, scrcpy) report state honestly: building, running, stopping, failed.

## Accessibility & Inclusion

Keyboard reachable: search focus, list navigation, Enter to open, standard dialog keys (Enter/Esc). Dark and light themes both maintain readable contrast.
