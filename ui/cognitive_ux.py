"""
cognitive_ux.py — ROS v6.0 Cognitive Psychology-Native UX
===========================================================
"A calm external cognitive cortex."

이 모듈은 인지심리학 원칙을 PyQt6 위젯으로 구현합니다:

A. ConfidenceBadge          — 신뢰도/불확실성 시각화
B. ProvenanceTrail          — AI 추론 근거 투명성 패널
C. AbstractionLevelBar      — 현재 추상화 레벨 인디케이터
D. CognitiveLoadGuard       — 작업 기억 보호 (Progressive Disclosure)
E. CalmMonetizationWidget   — 인지 안전 수익화 (유휴 상태 전용)
F. FocusModeController      — 집중 모드 (광고·알림 자동 억제)
G. UncertaintyVisualizer    — 불확실성 스펙트럼 바
H. SemanticOrientationHUD   — 의미론적 방향감각 HUD
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)


# ══════════════════════════════════════════════════════════════════════════════
# Design Tokens — Catppuccin Mocha (calm, stable, intellectually grounded)
# ══════════════════════════════════════════════════════════════════════════════

class CogPalette:
    """인지적으로 안전한 색상 팔레트. 자극적 색상 배제."""
    # Base
    BASE    = "#1e1e2e"
    MANTLE  = "#181825"
    CRUST   = "#11111b"
    SURFACE = "#313244"
    OVERLAY = "#45475a"

    # Text
    TEXT    = "#cdd6f4"
    SUBTEXT = "#a6adc8"
    MUTED   = "#6c7086"

    # Semantic (calm, not alarming)
    VERIFIED    = "#a6e3a1"   # green — verified knowledge
    INFERRED    = "#89b4fa"   # blue  — inferred abstraction
    SPECULATIVE = "#f9e2af"   # yellow — speculative hypothesis
    TENSION     = "#fab387"   # peach — research tension
    HALLUCINATION_RISK = "#f38ba8"  # red — hallucination risk
    UNRESOLVED  = "#cba6f7"   # lavender — unresolved assumption

    # Neutral
    ACCENT  = "#89dceb"   # sky
    LINK    = "#89b4fa"   # blue

    # Focus mode overlay
    FOCUS_DIM = "rgba(17, 17, 27, 0.92)"


class ConfidenceLevel(Enum):
    """AI 출력 신뢰도 레벨."""
    VERIFIED          = ("✓ Verified",        CogPalette.VERIFIED,    0.95)
    INFERRED          = ("~ Inferred",         CogPalette.INFERRED,    0.70)
    SPECULATIVE       = ("? Speculative",      CogPalette.SPECULATIVE, 0.45)
    TENSION           = ("⚡ Tension",          CogPalette.TENSION,     0.30)
    HALLUCINATION_RISK= ("⚠ Hallucination Risk", CogPalette.HALLUCINATION_RISK, 0.10)
    UNRESOLVED        = ("○ Unresolved",       CogPalette.UNRESOLVED,  0.20)

    def __init__(self, label: str, color: str, score: float):
        self.label = label
        self.color = color
        self.score = score


# ══════════════════════════════════════════════════════════════════════════════
# A. Confidence Badge
# ══════════════════════════════════════════════════════════════════════════════

class ConfidenceBadge(QLabel):
    """
    AI 출력의 신뢰도/불확실성을 시각적으로 표시하는 배지.
    사용자가 AI에 심리적으로 압도되지 않도록 명확한 구분 제공.
    """

    def __init__(self, level: ConfidenceLevel = ConfidenceLevel.INFERRED, parent=None):
        super().__init__(parent)
        self.set_level(level)
        self.setFixedHeight(20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)

    def set_level(self, level: ConfidenceLevel):
        self._level = level
        self.setText(level.label)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {level.color}22;
                color: {level.color};
                border: 1px solid {level.color}66;
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        self.setToolTip(self._build_tooltip(level))

    def _build_tooltip(self, level: ConfidenceLevel) -> str:
        descriptions = {
            ConfidenceLevel.VERIFIED:
                "Verified knowledge: directly extracted from source material.",
            ConfidenceLevel.INFERRED:
                "Inferred abstraction: derived by AI reasoning. Cross-check recommended.",
            ConfidenceLevel.SPECULATIVE:
                "Speculative hypothesis: AI-generated conjecture. Treat with caution.",
            ConfidenceLevel.TENSION:
                "Research tension: contradicts existing knowledge. Requires resolution.",
            ConfidenceLevel.HALLUCINATION_RISK:
                "Hallucination risk: low-confidence AI output. Manual verification required.",
            ConfidenceLevel.UNRESOLVED:
                "Unresolved assumption: key premise not yet validated.",
        }
        return descriptions.get(level, "")


# ══════════════════════════════════════════════════════════════════════════════
# B. Provenance Trail
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ProvenanceStep:
    """AI 추론 단계 기록."""
    step:        str
    source:      str
    confidence:  float
    timestamp:   str = field(default_factory=lambda: datetime.utcnow().strftime("%H:%M:%S"))


class ProvenanceTrail(QFrame):
    """
    AI가 왜 이 결론에 도달했는지 추론 근거를 투명하게 표시.
    블랙박스 인지 방지 — 사용자의 인지 신뢰 구축.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CogPalette.MANTLE};
                border: 1px solid {CogPalette.SURFACE};
                border-radius: 6px;
            }}
        """)
        self._steps: list[ProvenanceStep] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("🔍 Reasoning Provenance")
        title.setStyleSheet(f"color: {CogPalette.SUBTEXT}; font-size: 11px; font-weight: bold;")
        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setFixedSize(20, 20)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CogPalette.MUTED};
                border: none;
                font-size: 10px;
            }}
            QPushButton:hover {{ color: {CogPalette.TEXT}; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._toggle_btn)
        layout.addLayout(header)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 4, 0, 0)
        self._content_layout.setSpacing(3)
        layout.addWidget(self._content)

        self._collapsed = False

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        self._toggle_btn.setText("▶" if self._collapsed else "▼")

    def set_steps(self, steps: list[ProvenanceStep]):
        """추론 단계 설정 — 기존 내용 교체."""
        self._steps = steps
        # 기존 위젯 제거
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, step in enumerate(steps):
            row = self._build_step_row(i + 1, step)
            self._content_layout.addWidget(row)

    def _build_step_row(self, idx: int, step: ProvenanceStep) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        # 단계 번호
        num = QLabel(f"{idx}")
        num.setFixedSize(18, 18)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(f"""
            background-color: {CogPalette.SURFACE};
            color: {CogPalette.ACCENT};
            border-radius: 9px;
            font-size: 9px;
            font-weight: bold;
        """)

        # 단계 내용
        content_col = QVBoxLayout()
        content_col.setSpacing(0)
        step_lbl = QLabel(step.step)
        step_lbl.setStyleSheet(f"color: {CogPalette.TEXT}; font-size: 11px;")
        step_lbl.setWordWrap(True)
        source_lbl = QLabel(f"Source: {step.source}")
        source_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        content_col.addWidget(step_lbl)
        content_col.addWidget(source_lbl)

        # 신뢰도 바
        conf_bar = QProgressBar()
        conf_bar.setRange(0, 100)
        conf_bar.setValue(int(step.confidence * 100))
        conf_bar.setFixedSize(60, 6)
        conf_bar.setTextVisible(False)
        color = CogPalette.VERIFIED if step.confidence > 0.7 else (
            CogPalette.SPECULATIVE if step.confidence > 0.4 else CogPalette.HALLUCINATION_RISK
        )
        conf_bar.setStyleSheet(f"""
            QProgressBar {{ background: {CogPalette.SURFACE}; border-radius: 3px; border: none; }}
            QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}
        """)

        row_layout.addWidget(num)
        row_layout.addLayout(content_col, 1)
        row_layout.addWidget(conf_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def set_from_markdown(self, markdown: str):
        """Markdown 분석 결과에서 자동으로 Provenance 단계 추출."""
        steps = []
        lines = markdown.split('\n')
        for line in lines:
            if line.startswith('## ') or line.startswith('### '):
                section = line.lstrip('#').strip()
                if any(k in section for k in ['Identification', 'Causal', 'Algorithm', 'Assumption']):
                    steps.append(ProvenanceStep(
                        step=section,
                        source="LLM extraction from paper",
                        confidence=0.75,
                    ))
                elif any(k in section for k in ['Heterogeneity', 'CATE', 'Extension']):
                    steps.append(ProvenanceStep(
                        step=section,
                        source="LLM inference",
                        confidence=0.55,
                    ))
        if steps:
            self.set_steps(steps[:6])  # 최대 6단계 (작업 기억 보호)


# ══════════════════════════════════════════════════════════════════════════════
# C. Abstraction Level Bar
# ══════════════════════════════════════════════════════════════════════════════

class AbstractionLevelBar(QWidget):
    """
    현재 보고 있는 추상화 레벨을 시각적으로 표시.
    사용자가 항상 '어느 추상화 레이어에 있는지' 인식하도록 지원.
    """

    LEVELS = [
        ("Raw Data",       CogPalette.MUTED),
        ("Observation",    CogPalette.SUBTEXT),
        ("Pattern",        CogPalette.INFERRED),
        ("Concept",        CogPalette.ACCENT),
        ("Theory",         CogPalette.VERIFIED),
        ("Paradigm",       CogPalette.SPECULATIVE),
    ]

    level_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 2  # 기본: Pattern
        self._setup_ui()
        self.setFixedHeight(28)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(2)

        prefix = QLabel("Layer:")
        prefix.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        layout.addWidget(prefix)

        self._btns: list[QPushButton] = []
        for i, (name, color) in enumerate(self.LEVELS):
            btn = QPushButton(name)
            btn.setFixedHeight(20)
            btn.setCheckable(True)
            btn.setProperty("level_idx", i)
            btn.setProperty("level_color", color)
            btn.clicked.connect(lambda checked, idx=i: self._on_level_click(idx))
            self._btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        self._update_styles()

    def _on_level_click(self, idx: int):
        self._current = idx
        self._update_styles()
        self.level_changed.emit(idx)

    def _update_styles(self):
        for i, (btn, (name, color)) in enumerate(zip(self._btns, self.LEVELS)):
            if i == self._current:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color}33;
                        color: {color};
                        border: 1px solid {color}88;
                        border-radius: 4px;
                        font-size: 10px;
                        padding: 0 6px;
                        font-weight: bold;
                    }}
                """)
                btn.setChecked(True)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {CogPalette.MUTED};
                        border: 1px solid {CogPalette.SURFACE};
                        border-radius: 4px;
                        font-size: 10px;
                        padding: 0 6px;
                    }}
                    QPushButton:hover {{
                        color: {CogPalette.SUBTEXT};
                        border-color: {CogPalette.OVERLAY};
                    }}
                """)
                btn.setChecked(False)

    def set_level(self, idx: int):
        self._current = max(0, min(idx, len(self.LEVELS) - 1))
        self._update_styles()

    def current_level_name(self) -> str:
        return self.LEVELS[self._current][0]


# ══════════════════════════════════════════════════════════════════════════════
# D. Cognitive Load Guard (Progressive Disclosure)
# ══════════════════════════════════════════════════════════════════════════════

class CognitiveLoadGuard(QWidget):
    """
    Progressive Semantic Disclosure 구현.
    한 번에 너무 많은 정보를 노출하지 않도록 단계적으로 공개.
    최대 동시 표시 항목: 7 ± 2 (Miller's Law)
    """

    MAX_VISIBLE = 5  # 보수적으로 5개 제한

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._items: list[QWidget] = []
        self._visible_count = self.MAX_VISIBLE
        self._setup_ui()

    def _setup_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._header = QHBoxLayout()
        self._title_lbl = QLabel(self._title)
        self._title_lbl.setStyleSheet(
            f"color: {CogPalette.SUBTEXT}; font-size: 11px; font-weight: bold;"
        )
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        self._expand_btn = QPushButton("Show more")
        self._expand_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CogPalette.LINK};
                border: none;
                font-size: 10px;
                text-decoration: underline;
            }}
            QPushButton:hover {{ color: {CogPalette.ACCENT}; }}
        """)
        self._expand_btn.clicked.connect(self._expand)
        self._expand_btn.hide()

        self._header.addWidget(self._title_lbl)
        self._header.addWidget(self._count_lbl)
        self._header.addStretch()
        self._header.addWidget(self._expand_btn)
        self._layout.addLayout(self._header)

        self._items_container = QVBoxLayout()
        self._items_container.setSpacing(2)
        self._layout.addLayout(self._items_container)

    def add_item(self, widget: QWidget):
        self._items.append(widget)
        self._items_container.addWidget(widget)
        self._apply_visibility()

    def _apply_visibility(self):
        total = len(self._items)
        for i, item in enumerate(self._items):
            item.setVisible(i < self._visible_count)

        hidden = total - min(self._visible_count, total)
        if hidden > 0:
            self._expand_btn.setText(f"Show {hidden} more...")
            self._expand_btn.show()
        else:
            self._expand_btn.hide()

        self._count_lbl.setText(
            f"({min(self._visible_count, total)}/{total})"
            if total > self.MAX_VISIBLE else ""
        )

    def _expand(self):
        self._visible_count += self.MAX_VISIBLE
        self._apply_visibility()

    def clear_items(self):
        self._items.clear()
        self._visible_count = self.MAX_VISIBLE
        while self._items_container.count():
            item = self._items_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ══════════════════════════════════════════════════════════════════════════════
# E. Calm Monetization Widget
# ══════════════════════════════════════════════════════════════════════════════

class CalmMonetizationWidget(QFrame):
    """
    인지 안전 수익화 위젯.
    - 유휴 상태에서만 표시
    - Focus Mode 시 자동 숨김
    - 연구 관련 스폰서만 표시
    - 명확한 스폰서 레이블
    - 주의력 침해 없음
    """

    # 연구 친화적 스폰서 예시 (실제 구현 시 외부 설정으로 대체)
    SAMPLE_SPONSORS = [
        {
            "name": "Stata/MP",
            "category": "Econometrics Software",
            "message": "Professional econometric analysis",
            "url": "https://stata.com",
        },
        {
            "name": "NBER Working Papers",
            "category": "Research Infrastructure",
            "message": "Access 35,000+ working papers",
            "url": "https://nber.org",
        },
        {
            "name": "AWS Research Credits",
            "category": "Cloud Computing",
            "message": "GPU credits for researchers",
            "url": "https://aws.amazon.com/research-credits",
        },
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._focus_mode = False
        self._is_idle = False
        self._setup_ui()
        self.hide()  # 기본적으로 숨김

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CogPalette.MANTLE};
                border: 1px solid {CogPalette.SURFACE};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 스폰서 레이블 (명확한 표시)
        sponsor_header = QHBoxLayout()
        sponsor_tag = QLabel("SPONSOR")
        sponsor_tag.setStyleSheet(f"""
            color: {CogPalette.MUTED};
            font-size: 9px;
            font-weight: bold;
            letter-spacing: 1px;
            background: {CogPalette.SURFACE};
            border-radius: 3px;
            padding: 1px 5px;
        """)
        dismiss_btn = QPushButton("×")
        dismiss_btn.setFixedSize(16, 16)
        dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CogPalette.MUTED};
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{ color: {CogPalette.TEXT}; }}
        """)
        dismiss_btn.clicked.connect(self.hide)
        sponsor_header.addWidget(sponsor_tag)
        sponsor_header.addStretch()
        sponsor_header.addWidget(dismiss_btn)
        layout.addLayout(sponsor_header)

        # 스폰서 내용
        self._sponsor_name = QLabel("")
        self._sponsor_name.setStyleSheet(
            f"color: {CogPalette.TEXT}; font-size: 12px; font-weight: bold;"
        )
        self._sponsor_category = QLabel("")
        self._sponsor_category.setStyleSheet(
            f"color: {CogPalette.ACCENT}; font-size: 10px;"
        )
        self._sponsor_msg = QLabel("")
        self._sponsor_msg.setStyleSheet(
            f"color: {CogPalette.SUBTEXT}; font-size: 11px;"
        )
        self._sponsor_msg.setWordWrap(True)

        layout.addWidget(self._sponsor_name)
        layout.addWidget(self._sponsor_category)
        layout.addWidget(self._sponsor_msg)

        # 후원 버튼 (조용한 CTA)
        support_btn = QPushButton("Support this research ecosystem →")
        support_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CogPalette.LINK};
                border: none;
                font-size: 10px;
                text-align: left;
            }}
            QPushButton:hover {{ color: {CogPalette.ACCENT}; }}
        """)
        layout.addWidget(support_btn)

    def show_sponsor(self, sponsor: Optional[dict] = None):
        """스폰서 표시 — Focus Mode 시 무시."""
        if self._focus_mode:
            return
        if sponsor is None:
            sponsor = random.choice(self.SAMPLE_SPONSORS)
        self._sponsor_name.setText(sponsor.get("name", ""))
        self._sponsor_category.setText(sponsor.get("category", ""))
        self._sponsor_msg.setText(sponsor.get("message", ""))
        self.show()

    def set_focus_mode(self, active: bool):
        """Focus Mode 활성화 시 즉시 숨김."""
        self._focus_mode = active
        if active:
            self.hide()

    def set_idle(self, idle: bool):
        """유휴 상태 변경 — 유휴 시에만 표시 허용."""
        self._is_idle = idle
        if idle and not self._focus_mode:
            self.show_sponsor()
        elif not idle:
            self.hide()


# ══════════════════════════════════════════════════════════════════════════════
# F. Focus Mode Controller
# ══════════════════════════════════════════════════════════════════════════════

class FocusModeController(QWidget):
    """
    집중 모드 컨트롤러.
    활성화 시:
    - 광고/스폰서 자동 억제
    - 인프라 대시보드 숨김
    - 볼트 탐색기 최소화
    - 상태바 단순화
    - 조용한 시각적 환경 유지
    """

    focus_activated   = pyqtSignal()
    focus_deactivated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self._managed_widgets: list[QWidget] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._btn = QPushButton("◎  Focus")
        self._btn.setCheckable(True)
        self._btn.setFixedHeight(28)
        self._btn.setStyleSheet(self._btn_style(False))
        self._btn.toggled.connect(self._on_toggle)
        layout.addWidget(self._btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        layout.addWidget(self._status_lbl)

    def _btn_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background-color: {CogPalette.VERIFIED}22;
                    color: {CogPalette.VERIFIED};
                    border: 1px solid {CogPalette.VERIFIED}66;
                    border-radius: 6px;
                    font-size: 11px;
                    padding: 0 12px;
                    font-weight: bold;
                }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {CogPalette.MUTED};
                border: 1px solid {CogPalette.SURFACE};
                border-radius: 6px;
                font-size: 11px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                color: {CogPalette.TEXT};
                border-color: {CogPalette.OVERLAY};
            }}
        """

    def _on_toggle(self, checked: bool):
        self._active = checked
        self._btn.setStyleSheet(self._btn_style(checked))
        self._btn.setText("◉  Focus Active" if checked else "◎  Focus")
        self._status_lbl.setText("Ads suppressed · Deep work mode" if checked else "")

        # 관리 위젯에 포커스 모드 전파
        for widget in self._managed_widgets:
            if hasattr(widget, 'set_focus_mode'):
                widget.set_focus_mode(checked)
            elif hasattr(widget, 'setVisible'):
                widget.setVisible(not checked)

        if checked:
            self.focus_activated.emit()
        else:
            self.focus_deactivated.emit()

    def register_widget(self, widget: QWidget):
        """Focus Mode 시 숨길 위젯 등록."""
        self._managed_widgets.append(widget)

    @property
    def is_active(self) -> bool:
        return self._active


# ══════════════════════════════════════════════════════════════════════════════
# G. Uncertainty Visualizer
# ══════════════════════════════════════════════════════════════════════════════

class UncertaintyVisualizer(QWidget):
    """
    불확실성 스펙트럼 바.
    인간 인지가 숨겨진 불확실성을 처리하지 못하므로
    항상 명시적으로 시각화.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._scores: dict[str, float] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        label = QLabel("Certainty Spectrum:")
        label.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        layout.addWidget(label)

        self._segments: dict[str, QLabel] = {}
        segments = [
            ("Verified",   CogPalette.VERIFIED),
            ("Inferred",   CogPalette.INFERRED),
            ("Speculative",CogPalette.SPECULATIVE),
            ("Unresolved", CogPalette.UNRESOLVED),
        ]
        for name, color in segments:
            seg_layout = QVBoxLayout()
            seg_layout.setSpacing(1)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedSize(50, 6)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{ background: {CogPalette.SURFACE}; border-radius: 3px; border: none; }}
                QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}
            """)
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color: {color}; font-size: 9px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            seg_layout.addWidget(bar)
            seg_layout.addWidget(lbl)
            self._segments[name] = bar
            layout.addLayout(seg_layout)

        layout.addStretch()

    def set_scores(self, verified: float, inferred: float, speculative: float, unresolved: float):
        """각 카테고리의 비율 설정 (0-1)."""
        mapping = {
            "Verified":    verified,
            "Inferred":    inferred,
            "Speculative": speculative,
            "Unresolved":  unresolved,
        }
        for name, score in mapping.items():
            if name in self._segments:
                self._segments[name].setValue(int(score * 100))

    def analyze_markdown(self, markdown: str):
        """Markdown 내용에서 불확실성 점수 자동 추출."""
        text = markdown.lower()
        total = max(len(text), 1)

        verified_kw    = ['verified', 'confirmed', 'established', 'proven', 'empirical']
        inferred_kw    = ['inferred', 'suggests', 'implies', 'likely', 'consistent with']
        speculative_kw = ['speculative', 'hypothesize', 'conjecture', 'possible', 'might']
        unresolved_kw  = ['unresolved', 'unclear', 'unknown', 'open question', 'tension']

        def score(kws):
            return min(sum(text.count(k) for k in kws) * 0.15, 1.0)

        self.set_scores(
            verified    = score(verified_kw),
            inferred    = score(inferred_kw),
            speculative = score(speculative_kw),
            unresolved  = score(unresolved_kw),
        )


# ══════════════════════════════════════════════════════════════════════════════
# H. Semantic Orientation HUD
# ══════════════════════════════════════════════════════════════════════════════

class SemanticOrientationHUD(QFrame):
    """
    의미론적 방향감각 HUD.
    사용자가 항상 '지금 어디에 있는지' 인식하도록:
    - 현재 노트 위치 (폴더 경로)
    - 활성 연구 긴장
    - 탐색 중인 가설 체인
    - 연결된 개념 수
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CogPalette.MANTLE};
                border-bottom: 1px solid {CogPalette.SURFACE};
            }}
        """)
        self.setFixedHeight(32)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(16)

        # 현재 위치 (Semantic Breadcrumb)
        self._location_lbl = QLabel("📍 —")
        self._location_lbl.setStyleSheet(f"color: {CogPalette.SUBTEXT}; font-size: 11px;")

        # 활성 연구 긴장
        self._tension_lbl = QLabel("⚡ —")
        self._tension_lbl.setStyleSheet(f"color: {CogPalette.TENSION}; font-size: 11px;")

        # 연결 수
        self._links_lbl = QLabel("🔗 0 links")
        self._links_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 11px;")

        # 현재 분석 모드
        self._mode_lbl = QLabel("◎ —")
        self._mode_lbl.setStyleSheet(f"color: {CogPalette.ACCENT}; font-size: 11px;")

        layout.addWidget(self._location_lbl)
        layout.addWidget(self._separator())
        layout.addWidget(self._tension_lbl)
        layout.addWidget(self._separator())
        layout.addWidget(self._links_lbl)
        layout.addStretch()
        layout.addWidget(self._mode_lbl)

    def _separator(self) -> QLabel:
        sep = QLabel("·")
        sep.setStyleSheet(f"color: {CogPalette.SURFACE}; font-size: 14px;")
        return sep

    def update_context(
        self,
        location: str = "",
        tension: str = "",
        link_count: int = 0,
        mode: str = "",
    ):
        if location:
            self._location_lbl.setText(f"📍 {location[:40]}")
        if tension:
            self._tension_lbl.setText(f"⚡ {tension[:30]}")
        else:
            self._tension_lbl.setText("⚡ No active tension")
        self._links_lbl.setText(f"🔗 {link_count} links")
        if mode:
            self._mode_lbl.setText(f"◎ {mode}")


# ══════════════════════════════════════════════════════════════════════════════
# Composite: Cognitive Status Bar
# ══════════════════════════════════════════════════════════════════════════════

class CognitiveStatusBar(QFrame):
    """
    메인 윈도우 하단 상태바.
    인지적으로 안전한 정보만 표시 — 과부하 방지.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CogPalette.CRUST};
                border-top: 1px solid {CogPalette.SURFACE};
            }}
        """)
        self.setFixedHeight(26)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        layout.setSpacing(16)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {CogPalette.SUBTEXT}; font-size: 10px;")

        self._model_lbl = QLabel("")
        self._model_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")

        self._vault_lbl = QLabel("")
        self._vault_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")

        self._version_lbl = QLabel("ROS v6.0")
        self._version_lbl.setStyleSheet(f"color: {CogPalette.SURFACE}; font-size: 10px;")

        layout.addWidget(self._status_lbl)
        layout.addWidget(self._separator())
        layout.addWidget(self._model_lbl)
        layout.addWidget(self._separator())
        layout.addWidget(self._vault_lbl)
        layout.addStretch()
        layout.addWidget(self._version_lbl)

    def _separator(self) -> QLabel:
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {CogPalette.SURFACE}; font-size: 12px;")
        return sep

    def set_status(self, msg: str):
        self._status_lbl.setText(msg)

    def set_model(self, model: str):
        self._model_lbl.setText(f"⚡ {model}" if model else "")

    def set_vault(self, vault: str):
        import os
        if vault:
            name = os.path.basename(vault) or vault
            self._vault_lbl.setText(f"📂 {name}")
        else:
            self._vault_lbl.setText("No vault")
