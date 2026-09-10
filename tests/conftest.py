import os
import sys

import pytest


@pytest.fixture(scope="session")
def qt_app():
    qt_widgets = pytest.importorskip("PyQt6.QtWidgets", reason="legacy PyQt UI is optional")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return qt_widgets.QApplication.instance() or qt_widgets.QApplication(sys.argv)
