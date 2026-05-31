import os
import sys

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow, apply_dark_theme


def test_main_window_constructs_with_pyqt6_menu_actions():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)

    window = MainWindow()

    assert window.menuBar().actions()
    assert window.windowTitle()
