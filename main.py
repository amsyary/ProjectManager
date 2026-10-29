"""Project Manager - Desktop app to open projects in Cursor, VS Code or Antigravity."""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication

from services.project_service import ProjectService
from ui.main_window import MainWindow
from ui.theme import Theme, label_font


def main():
    if sys.platform == "win32":
        try:
            import ctypes

            # Own taskbar identity, so Windows shows our icon instead of python.exe's
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Amsyari.ProjectManager")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Project Manager")
    app.setFont(label_font())
    Theme.get().set_dark(ProjectService.get_theme() == "dark")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
