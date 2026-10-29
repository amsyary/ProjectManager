# ProjectManager

PySide6 (Qt) desktop app for opening projects/sub-projects in an editor, terminal, browser, or scrcpy. Packaged as a Windows exe with PyInstaller.

## Always build after a change

After adding a feature or fixing a bug, rebuild the exe so `dist\ProjectManager.exe` is never stale:

```powershell
py -m PyInstaller --clean --noconfirm ProjectManager.spec
```

- Before building, check whether `ProjectManager.exe` is running (`Get-Process ProjectManager`). If it is, the build can't overwrite the exe. Don't kill it yourself; ask the user to close it (or ask for permission to close it).
- After building, smoke-test: start `dist\ProjectManager.exe`, confirm a window titled "Project Manager" appears, then stop **all** `ProjectManager` processes (the one-file exe runs as two processes).
- Report the build result to the user; if it failed, show the error output.

## Environment gotchas

- Use `py` (Python 3.12), not `python`. The default `python` is 3.15, where packages may not be installed.
- Design direction and tokens live in `ui/theme.py`; the design system is documented in DESIGN.md (product context in PRODUCT.md).
- The exe keeps its own data in `dist\data\` and `dist\config\`. Running from source uses the repo's `data\` and `config\`. They are separate.
- `dist/` and `build/` are git-ignored; builds are never committed.
- `ProjectManager.spec` never bundles `config/` or `data/` (they hold personal projects and are created next to the exe on first run). Don't add them back: public releases would ship them.

## Releases

- `.github/workflows/release.yml` builds on Windows: the one-file portable exe, the folder build (`PM_ONEDIR=1`), then the Inno Setup installer from `installer/ProjectManager.iss`. A pushed `v*` tag publishes a GitHub Release; PRs and manual runs only upload artifacts.
- The installer is per-user (`%LOCALAPPDATA%\Programs\Project Manager`, no admin) because the app writes `data/` and `config/` next to its exe. Don't switch it to Program Files.
- Pushing a tag publishes a public release: only do it when the user asks.
