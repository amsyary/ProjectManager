# ProjectManager

Tkinter desktop app for opening projects/sub-projects in an editor, terminal, browser, or scrcpy. Packaged as a Windows exe with PyInstaller.

## Always build after a change

After adding a feature or fixing a bug, rebuild the exe so `dist\ProjectManager.exe` is never stale:

```powershell
$env:TCL_LIBRARY = $null; $env:TK_LIBRARY = $null
py -m PyInstaller --clean --noconfirm ProjectManager.spec
```

- Before building, check whether `ProjectManager.exe` is running (`Get-Process ProjectManager`). If it is, the build can't overwrite the exe. Don't kill it yourself; ask the user to close it (or ask for permission to close it).
- After building, smoke-test: start `dist\ProjectManager.exe`, confirm a window titled "Project Manager" appears, then stop **all** `ProjectManager` processes (the one-file exe runs as two processes).
- Report the build result to the user; if it failed, show the error output.

## Environment gotchas

- Use `py` (Python 3.12), not `python`. The default `python` is 3.15, where Pillow fails to import ("unknown slot ID 85").
- Shells started from the running exe inherit `TCL_LIBRARY`/`TK_LIBRARY` pointing at a PyInstaller temp folder, which breaks tkinter. Clear them before running or building (`env -u TCL_LIBRARY -u TK_LIBRARY py main.py` in bash).
- The exe keeps its own data in `dist\data\` and `dist\config\`. Running from source uses the repo's `data\` and `config\`. They are separate.
- `dist/` and `build/` are git-ignored; builds are never committed.
