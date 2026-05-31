"""
profile_dialog.py — Researcher Profile Editor
==============================================
연구자 프로필 편집: 연구 관심사, 선호 방법론, 활성 프로젝트, 미해결 질문
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QGroupBox, QDialogButtonBox, QTabWidget, QWidget,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from core import memory


class ProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("👤 연구자 프로필")
        self.setMinimumSize(600, 500)
        self._build_ui()
        self._load()

    def _build_ui(self):
        l = QVBoxLayout(self)
        hdr = QLabel("👤 Researcher Profile")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet("color:#89b4fa;padding:4px 0;")
        l.addWidget(hdr)
        l.addWidget(QLabel("ROS가 분석 시 참조하는 연구자 컨텍스트입니다. 자세할수록 더 정확한 분석이 생성됩니다."))

        tabs = QTabWidget()

        # 탭 1: 기본 정보
        t1 = QWidget(); tl = QVBoxLayout(t1)
        tl.addWidget(QLabel("이름:"))
        self.name_edit = QLineEdit(); self.name_edit.setPlaceholderText("연구자 이름")
        tl.addWidget(self.name_edit)
        tl.addWidget(QLabel("소속:"))
        self.affil_edit = QLineEdit(); self.affil_edit.setPlaceholderText("대학/연구소")
        tl.addWidget(self.affil_edit)
        tl.addWidget(QLabel("연구 분야:"))
        self.field_edit = QLineEdit(); self.field_edit.setPlaceholderText("예: Labor Economics, Causal Inference")
        tl.addWidget(self.field_edit)
        tabs.addTab(t1, "기본 정보")

        # 탭 2: 연구 관심사
        t2 = QWidget(); tl2 = QVBoxLayout(t2)
        tl2.addWidget(QLabel("연구 관심사 (줄바꿈으로 구분):"))
        self.interests_edit = QTextEdit()
        self.interests_edit.setPlaceholderText("예:\nMinimum wage effects\nDML with panel data\nHeterogeneous treatment effects")
        tl2.addWidget(self.interests_edit)
        tabs.addTab(t2, "연구 관심사")

        # 탭 3: 선호 방법론
        t3 = QWidget(); tl3 = QVBoxLayout(t3)
        tl3.addWidget(QLabel("선호 방법론 (줄바꿈으로 구분):"))
        self.methods_edit = QTextEdit()
        self.methods_edit.setPlaceholderText("예:\nDouble Machine Learning (DML)\nCausal Forest\nDifference-in-Differences\nInstrumental Variables")
        tl3.addWidget(self.methods_edit)
        tabs.addTab(t3, "선호 방법론")

        # 탭 4: 활성 프로젝트 & 미해결 질문
        t4 = QWidget(); tl4 = QVBoxLayout(t4)
        tl4.addWidget(QLabel("활성 프로젝트:"))
        self.projects_edit = QTextEdit()
        self.projects_edit.setPlaceholderText("예:\n- 최저임금 고용효과 DML 분석\n- 의료보험 접근성과 건강 결과")
        self.projects_edit.setMaximumHeight(120)
        tl4.addWidget(self.projects_edit)
        tl4.addWidget(QLabel("미해결 연구 질문:"))
        self.questions_edit = QTextEdit()
        self.questions_edit.setPlaceholderText("예:\n- 이질적 효과의 경제적 메커니즘은?\n- 외부 타당성 확보 방법?")
        tl4.addWidget(self.questions_edit)
        tabs.addTab(t4, "프로젝트 & 질문")

        l.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        l.addWidget(btns)

    def _load(self):
        p = memory.load_profile()
        self.name_edit.setText(p.get("name", ""))
        self.affil_edit.setText(p.get("affiliation", ""))
        self.field_edit.setText(p.get("field", ""))
        self.interests_edit.setPlainText("\n".join(p.get("interests", [])))
        self.methods_edit.setPlainText("\n".join(p.get("preferred_methods", [])))
        self.projects_edit.setPlainText("\n".join(p.get("active_projects", [])))
        self.questions_edit.setPlainText("\n".join(p.get("open_questions", [])))

    def _save(self):
        profile = {
            "name":              self.name_edit.text().strip(),
            "affiliation":       self.affil_edit.text().strip(),
            "field":             self.field_edit.text().strip(),
            "interests":         [l.strip() for l in self.interests_edit.toPlainText().splitlines() if l.strip()],
            "preferred_methods": [l.strip() for l in self.methods_edit.toPlainText().splitlines() if l.strip()],
            "active_projects":   [l.strip() for l in self.projects_edit.toPlainText().splitlines() if l.strip()],
            "open_questions":    [l.strip() for l in self.questions_edit.toPlainText().splitlines() if l.strip()],
        }
        memory.save_profile(profile)
        self.accept()
