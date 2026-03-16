"""Project Manager - Desktop app to open projects in Cursor or VS Code."""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui.main_window import MainWindow


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
