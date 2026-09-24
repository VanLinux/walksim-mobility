"""Punto de entrada de WalkSim Mobility."""

from __future__ import annotations

import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from walksim import __version__
from walksim.ui.main_window import MainWindow
from walksim.ui.styles import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WalkSim Mobility")
    app.setApplicationDisplayName(f"WalkSim Mobility {__version__}")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("VanLinux")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Mexico))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
