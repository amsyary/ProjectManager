# Project Manager

A desktop application to manage and quickly open your projects in Cursor or VS Code. Organize multiple projects with sub-projects, open them individually or all at once, and keep your most-used projects at the top.

## Purpose

Project Manager helps developers who work with many projects—especially those with multiple sub-projects (e.g., Flutter app + admin dashboard + cloud functions). Instead of navigating folders or remembering paths, you open the app, click a project, and open what you need in Cursor or VS Code with one click.

## Features

- **Grid view** – See all projects at a glance with optional custom icons
- **Sub-projects** – Each project can have multiple directories (e.g., Flutter, Admin Dashboard, Cloud Function, Web, Documentation)
- **Quick open** – Open sub-projects in Cursor or VS Code; open the main project folder in Windows Explorer
- **Project types** – Categorize sub-projects: Flutter, Admin Dashboard, Cloud Function, Web Version, Documentation, General, or Data File (.txt)
- **Most-used sorting** – Projects you open most often move to the top
- **Search** – Filter projects by name
- **Export/Import** – Backup and restore your project list as JSON
- **Data File (.txt)** – Add .txt files that open in Notepad

## Requirements

- Python 3.10+
- Pillow (for PNG/JPG icons)

## Installation

```bash
# Clone or download the project
cd ProjectManager

# Install dependencies
py -m pip install -r requirements.txt

# Run the app
py main.py
```

## Building a Windows Executable

```bash
py -m pip install pyinstaller
py -m PyInstaller --onefile --windowed --name ProjectManager --add-data config;config --add-data data;data --add-data assets;assets main.py
```

The executable will be in `dist/ProjectManager.exe`.

Or use the VS Code task: **Terminal → Run Task → Build: Windows executable**

## Usage

1. **Add a project** – Click "+ Add Project", enter a name, optionally set an icon and main project folder, then add sub-projects (directory + type).
2. **Open projects** – Click a project to see its sub-projects. Use "Project Folder" to open the main folder in Explorer, or "Open All" / "Open" to open sub-projects in Cursor or VS Code.
3. **Editor choice** – Use the dropdown at the top to switch between Cursor and VS Code. Your choice is saved.
4. **Edit/Delete** – Right-click a project card for Edit or Delete.

## Project Structure

```
ProjectManager/
├── main.py              # Entry point
├── config/              # Settings (editor preference)
├── data/                # Projects (projects.json)
├── assets/icons/        # Type icons (flutter.png, etc.)
├── models/              # Data models
├── services/            # Project & editor logic
└── ui/                  # Tkinter UI
```

## Icons

Place custom icons in `assets/icons/` with these names:

- `flutter.png`, `admin_dashboard.png`, `cloud_function.png`
- `web_version.png`, `documentation.png`, `general.png`, `data_txt.png`

## Author

**Amsyari**

Contact: [amsyary.skenza313@gmail.com](mailto:amsyary.skenza313@gmail.com)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
