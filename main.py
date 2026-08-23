"""
main.py — Research Operating System (ROS) Entry Point
실행: python main.py  |  bash run.sh  |  ROS.exe (Windows)
"""

import sys
import os

# 실제 최소 버전 가드 (audit F-03): core 모듈들이 datetime.UTC(3.11+)를 사용.
# 선언된 플랫폼보다 오래된 인터프리터에서는 조용히 망가지는 대신 명시적으로 중단.
if sys.version_info < (3, 11):
    sys.stderr.write(
        "Research Operating System requires Python 3.11 or newer "
        f"(found {sys.version.split()[0]}). Please upgrade Python.\n"
    )
    sys.exit(1)

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.main_window import MainWindow, apply_dark_theme


def main():
    # HiDPI 지원
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("Research Operating System")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("ROS")

    # 다크 테마 적용
    apply_dark_theme(app)

    # 기본 폰트 설정
    font = QFont()
    font.setFamily("Segoe UI" if sys.platform == "win32" else
                   "SF Pro Text" if sys.platform == "darwin" else
                   "Ubuntu")
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
