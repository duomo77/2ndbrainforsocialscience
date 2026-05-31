"""
cognitive_panels.py — ROS v6.0 Cognitive UX Panels
====================================================
인지심리학 원칙 기반 패널 컴포넌트:

A. FocusModeOverlay     — 집중 모드 오버레이 (주변 요소 dim처리)
B. SemanticBreadcrumb   — 의미론적 경로 탐색 위젯
C. EquationScaffold     — 수식 인지 부담 감소 패널
D. LocalGraphView       — 로컬 그래프 뷰어 (locality-bounded, 불안 방지)
E. ContradictionHighlighter — 모순 하이라이터
F. CognitiveResultPanel — 인지 안전 결과 패널 (신뢰도 레이어 통합)
"""

from __future__ import annotations

import re
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from ui.cognitive_ux import (
    CogPalette, ConfidenceBadge, ConfidenceLevel,
    ProvenanceTrail, ProvenanceStep,
    AbstractionLevelBar, UncertaintyVisualizer,
    CalmMonetizationWidget,
)


# ══════════════════════════════════════════════════════════════════════════════
# A. Focus Mode Overlay
# ══════════════════════════════════════════════════════════════════════════════

class FocusModeOverlay(QWidget):
    """
    집중 모드 활성화 시 비핵심 영역을 dim 처리.
    주의력 보존 — 핵심 작업 영역만 강조.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(f"background-color: rgba(17, 17, 27, 0.72);")
        self.hide()

    def activate(self):
        if self.parent():
            self.resize(self.parent().size())
        self.show()
        self.raise_()

    def deactivate(self):
        self.hide()


# ══════════════════════════════════════════════════════════════════════════════
# B. Semantic Breadcrumb
# ══════════════════════════════════════════════════════════════════════════════

class SemanticBreadcrumb(QFrame):
    """
    의미론적 경로 탐색 위젯.
    사용자가 항상 개념적 위치를 인식하도록.
    예: Papers > Econometrics > DML > Nuisance Parameters
    """

    node_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CogPalette.MANTLE};
                border-bottom: 1px solid {CogPalette.SURFACE};
            }}
        """)
        self.setFixedHeight(30)
        self._crumbs: list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 4, 12, 4)
        self._layout.setSpacing(4)

        home_btn = QPushButton("⌂")
        home_btn.setFixedSize(20, 20)
        home_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CogPalette.MUTED};
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{ color: {CogPalette.TEXT}; }}
        """)
        home_btn.clicked.connect(lambda: self.node_clicked.emit("root"))
        self._layout.addWidget(home_btn)

        self._crumb_container = QHBoxLayout()
        self._crumb_container.setSpacing(2)
        self._layout.addLayout(self._crumb_container)
        self._layout.addStretch()

    def set_path(self, path: list[str]):
        """경로 설정. 예: ['Papers', 'Econometrics', 'DML']"""
        self._crumbs = path
        # 기존 크럼 제거
        while self._crumb_container.count():
            item = self._crumb_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 최대 4개 표시 (작업 기억 보호)
        display_path = path[-4:] if len(path) > 4 else path
        if len(path) > 4:
            ellipsis = QLabel("… ›")
            ellipsis.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 11px;")
            self._crumb_container.addWidget(ellipsis)

        for i, crumb in enumerate(display_path):
            btn = QPushButton(crumb)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {'#' + CogPalette.TEXT[1:] if i == len(display_path)-1 else CogPalette.SUBTEXT};
                    border: none;
                    font-size: 11px;
                    font-weight: {'bold' if i == len(display_path)-1 else 'normal'};
                    padding: 0 2px;
                }}
                QPushButton:hover {{ color: {CogPalette.ACCENT}; }}
            """)
            btn.clicked.connect(lambda checked, c=crumb: self.node_clicked.emit(c))
            self._crumb_container.addWidget(btn)

            if i < len(display_path) - 1:
                sep = QLabel("›")
                sep.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 11px;")
                self._crumb_container.addWidget(sep)

    def push(self, node: str):
        """경로에 노드 추가."""
        self._crumbs.append(node)
        self.set_path(self._crumbs)

    def pop(self):
        """마지막 노드 제거."""
        if self._crumbs:
            self._crumbs.pop()
            self.set_path(self._crumbs)


# ══════════════════════════════════════════════════════════════════════════════
# C. Equation Scaffold
# ══════════════════════════════════════════════════════════════════════════════

class EquationScaffold(QFrame):
    """
    수식 인지 부담 감소 패널.
    LaTeX 수식을 구조적으로 분해하여 표시:
    - 수식 자체
    - 각 항의 의미 설명
    - 직교성 조건
    - 추정 방법
    수학적 인지 부담을 외부화.
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
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 헤더
        header = QHBoxLayout()
        title = QLabel("📐 Mathematical Scaffold")
        title.setStyleSheet(
            f"color: {CogPalette.INFERRED}; font-size: 11px; font-weight: bold;"
        )
        self._toggle = QPushButton("▼")
        self._toggle.setFixedSize(20, 20)
        self._toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {CogPalette.MUTED};
                border: none; font-size: 10px;
            }}
            QPushButton:hover {{ color: {CogPalette.TEXT}; }}
        """)
        self._toggle.clicked.connect(self._on_toggle)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._toggle)
        layout.addLayout(header)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        # 수식 표시 영역
        eq_label = QLabel("Core Equation:")
        eq_label.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        self._equation_lbl = QLabel("")
        self._equation_lbl.setStyleSheet(f"""
            color: {CogPalette.TEXT};
            font-family: 'Courier New', monospace;
            font-size: 12px;
            background: {CogPalette.SURFACE};
            border-radius: 4px;
            padding: 6px 10px;
        """)
        self._equation_lbl.setWordWrap(True)
        self._equation_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        # 항 설명 영역
        terms_label = QLabel("Term Decomposition:")
        terms_label.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        self._terms_area = QTextEdit()
        self._terms_area.setReadOnly(True)
        self._terms_area.setFixedHeight(80)
        self._terms_area.setStyleSheet(f"""
            QTextEdit {{
                background: {CogPalette.SURFACE};
                color: {CogPalette.SUBTEXT};
                border: none;
                border-radius: 4px;
                font-size: 11px;
                padding: 4px;
            }}
        """)

        # 직교성 조건
        orth_label = QLabel("Orthogonality Condition:")
        orth_label.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        self._orth_lbl = QLabel("")
        self._orth_lbl.setStyleSheet(f"""
            color: {CogPalette.VERIFIED};
            font-family: 'Courier New', monospace;
            font-size: 11px;
            background: {CogPalette.VERIFIED}11;
            border-left: 2px solid {CogPalette.VERIFIED};
            padding: 4px 8px;
        """)
        self._orth_lbl.setWordWrap(True)

        content_layout.addWidget(eq_label)
        content_layout.addWidget(self._equation_lbl)
        content_layout.addWidget(terms_label)
        content_layout.addWidget(self._terms_area)
        content_layout.addWidget(orth_label)
        content_layout.addWidget(self._orth_lbl)

        layout.addWidget(self._content)
        self._collapsed = False

    def _on_toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        self._toggle.setText("▶" if self._collapsed else "▼")

    def set_equation(self, equation: str, terms: dict[str, str], orthogonality: str):
        """수식 및 항 설명 설정."""
        self._equation_lbl.setText(equation)
        terms_text = "\n".join(f"  {k}: {v}" for k, v in terms.items())
        self._terms_area.setPlainText(terms_text)
        self._orth_lbl.setText(orthogonality)

    def extract_from_markdown(self, markdown: str):
        """Markdown에서 수식 자동 추출."""
        # LaTeX 블록 추출
        latex_blocks = re.findall(r'\$\$(.+?)\$\$', markdown, re.DOTALL)
        inline_latex = re.findall(r'\$([^$\n]+)\$', markdown)

        if latex_blocks:
            eq = latex_blocks[0].strip()
        elif inline_latex:
            eq = inline_latex[0].strip()
        else:
            eq = "No equation found"

        # 직교성 조건 추출
        orth_match = re.search(
            r'[Oo]rthogonality[^:]*:?\s*(.+?)(?:\n|$)', markdown
        )
        orth = orth_match.group(1).strip() if orth_match else "E[ψ(W; θ, η)] = 0"

        # 기본 항 설명
        terms = {}
        if 'theta' in markdown.lower() or 'θ' in markdown:
            terms['θ'] = 'Treatment Effect (ATE/CATE)'
        if 'eta' in markdown.lower() or 'η' in markdown:
            terms['η'] = 'Nuisance Parameters'
        if 'epsilon' in markdown.lower() or 'ε' in markdown:
            terms['ε'] = 'Residual / Error Term'
        if not terms:
            terms = {'θ': 'Parameter of interest', 'X': 'Controls/Confounders'}

        self.set_equation(eq, terms, orth)


# ══════════════════════════════════════════════════════════════════════════════
# D. Local Graph View (Locality-Bounded, 불안 방지)
# ══════════════════════════════════════════════════════════════════════════════

class LocalGraphView(QFrame):
    """
    로컬 그래프 뷰어.
    - 최대 표시 노드: 12개 (그래프 불안 방지)
    - 현재 노트 중심 ego-network만 표시
    - 텍스트 기반 그래프 (PyQt6 Canvas 없이도 명확)
    - 추상화 레벨별 필터링
    """

    MAX_NODES = 12

    node_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CogPalette.MANTLE};
                border: 1px solid {CogPalette.SURFACE};
                border-radius: 6px;
            }}
        """)
        self._nodes: list[dict] = []
        self._center: str = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 헤더
        header = QHBoxLayout()
        title = QLabel("🕸 Local Knowledge Graph")
        title.setStyleSheet(
            f"color: {CogPalette.SUBTEXT}; font-size: 11px; font-weight: bold;"
        )
        self._node_count = QLabel("0 nodes")
        self._node_count.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._node_count)
        layout.addLayout(header)

        # 중심 노트 표시
        self._center_lbl = QLabel("")
        self._center_lbl.setStyleSheet(f"""
            color: {CogPalette.ACCENT};
            font-size: 12px;
            font-weight: bold;
            background: {CogPalette.ACCENT}11;
            border-left: 3px solid {CogPalette.ACCENT};
            padding: 4px 8px;
            border-radius: 0 4px 4px 0;
        """)
        layout.addWidget(self._center_lbl)

        # 연결 노드 목록 (스크롤 가능)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: {CogPalette.SURFACE}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {CogPalette.OVERLAY}; border-radius: 3px;
            }}
        """)
        self._nodes_widget = QWidget()
        self._nodes_layout = QVBoxLayout(self._nodes_widget)
        self._nodes_layout.setContentsMargins(0, 0, 0, 0)
        self._nodes_layout.setSpacing(2)
        scroll.setWidget(self._nodes_widget)
        layout.addWidget(scroll)

        # 그래프 불안 방지 메시지
        self._limit_lbl = QLabel("")
        self._limit_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")
        layout.addWidget(self._limit_lbl)

    def set_graph(self, center: str, connections: list[dict]):
        """
        그래프 설정.
        connections: [{'node': str, 'relation': str, 'strength': float}]
        """
        self._center = center
        self._nodes = connections

        self._center_lbl.setText(f"◉ {center}")

        # 기존 노드 제거
        while self._nodes_layout.count():
            item = self._nodes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 최대 MAX_NODES개만 표시 (locality bounding)
        display = connections[:self.MAX_NODES]
        for conn in display:
            row = self._build_node_row(conn)
            self._nodes_layout.addWidget(row)

        self._nodes_layout.addStretch()

        # 노드 수 표시
        total = len(connections)
        shown = len(display)
        self._node_count.setText(f"{shown}/{total} nodes")

        if total > self.MAX_NODES:
            hidden = total - self.MAX_NODES
            self._limit_lbl.setText(
                f"+ {hidden} more connections (hidden to preserve focus)"
            )
        else:
            self._limit_lbl.setText("")

    def _build_node_row(self, conn: dict) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(8)

        # 관계 유형 아이콘
        relation = conn.get('relation', 'related')
        icons = {
            'cites': '📎', 'extends': '→', 'contradicts': '⚡',
            'uses': '⚙', 'defines': '📐', 'related': '·',
        }
        icon_lbl = QLabel(icons.get(relation, '·'))
        icon_lbl.setFixedWidth(16)
        icon_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 11px;")

        # 노드 버튼
        node_name = conn.get('node', '')
        btn = QPushButton(f"[[{node_name}]]")
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CogPalette.LINK};
                border: none;
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {CogPalette.ACCENT};
                text-decoration: underline;
            }}
        """)
        btn.clicked.connect(lambda: self.node_selected.emit(node_name))

        # 관계 레이블
        rel_lbl = QLabel(relation)
        rel_lbl.setStyleSheet(f"color: {CogPalette.MUTED}; font-size: 10px;")

        # 강도 바
        strength = conn.get('strength', 0.5)
        strength_bar = QFrame()
        strength_bar.setFixedSize(int(strength * 40), 4)
        strength_bar.setStyleSheet(f"""
            background: {CogPalette.INFERRED};
            border-radius: 2px;
        """)

        row_layout.addWidget(icon_lbl)
        row_layout.addWidget(btn, 1)
        row_layout.addWidget(rel_lbl)
        row_layout.addWidget(strength_bar)
        return row

    def extract_from_markdown(self, title: str, markdown: str):
        """Markdown에서 WikiLink 추출하여 그래프 구성."""
        links = re.findall(r'\[\[([^\]]+)\]\]', markdown)
        connections = []
        seen = set()
        for link in links:
            if link not in seen and link != title:
                seen.add(link)
                # 관계 유형 추론
                context_idx = markdown.find(f'[[{link}]]')
                context = markdown[max(0, context_idx-50):context_idx].lower()
                if 'contradict' in context or 'tension' in context:
                    relation = 'contradicts'
                elif 'extend' in context or 'build' in context:
                    relation = 'extends'
                elif 'use' in context or 'apply' in context:
                    relation = 'uses'
                elif 'define' in context or 'assume' in context:
                    relation = 'defines'
                else:
                    relation = 'related'
                connections.append({
                    'node': link,
                    'relation': relation,
                    'strength': 0.7,
                })
        self.set_graph(title or "Current Note", connections)


# ══════════════════════════════════════════════════════════════════════════════
# E. Contradiction Highlighter (Syntax Highlighter)
# ══════════════════════════════════════════════════════════════════════════════

class ContradictionHighlighter(QSyntaxHighlighter):
    """
    Markdown 텍스트에서 모순·긴장 키워드를 시각적으로 강조.
    사용자가 연구 긴장을 즉시 인식하도록.
    """

    PATTERNS = [
        # 모순/긴장 (주황)
        (r'\b(contradict|tension|conflict|inconsistent|paradox|puzzle)\w*\b',
         CogPalette.TENSION),
        # 불확실/추측 (노랑)
        (r'\b(speculative|hypothesize|conjecture|possible|might|could|unclear)\b',
         CogPalette.SPECULATIVE),
        # 검증됨 (초록)
        (r'\b(verified|confirmed|established|robust|significant)\b',
         CogPalette.VERIFIED),
        # 환각 위험 (빨강)
        (r'\b(hallucination|fabricated|unverified|caution)\b',
         CogPalette.HALLUCINATION_RISK),
        # WikiLink (파랑)
        (r'\[\[[^\]]+\]\]', CogPalette.LINK),
        # LaTeX 수식 (연보라)
        (r'\$[^$\n]+\$', CogPalette.UNRESOLVED),
        # YAML Frontmatter 키 (회색)
        (r'^[a-z_]+(?=:)', CogPalette.MUTED),
    ]

    def __init__(self, document):
        super().__init__(document)
        self._rules = []
        for pattern, color in self.PATTERNS:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if color in (CogPalette.TENSION, CogPalette.HALLUCINATION_RISK):
                fmt.setFontWeight(QFont.Weight.Bold)
            self._rules.append((re.compile(pattern, re.IGNORECASE), fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


# ══════════════════════════════════════════════════════════════════════════════
# F. Cognitive Result Panel
# ══════════════════════════════════════════════════════════════════════════════

class CognitiveResultPanel(QWidget):
    """
    인지 안전 결과 패널.
    분석 결과를 인지심리학 원칙에 따라 표시:
    - 신뢰도 레이어 (ConfidenceBadge)
    - 불확실성 스펙트럼 (UncertaintyVisualizer)
    - 수식 스캐폴드 (EquationScaffold)
    - 로컬 그래프 뷰 (LocalGraphView)
    - Provenance Trail
    - 편집 가능한 Markdown 에디터
    - 인지 안전 수익화 (유휴 시)
    """

    save_requested = pyqtSignal(str)  # markdown content

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_markdown = ""
        self._current_title = ""
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 상단: 신뢰도 + 불확실성 바 ──────────────────────────────────────
        top_bar = QFrame()
        top_bar.setStyleSheet(f"""
            QFrame {{
                background: {CogPalette.MANTLE};
                border-bottom: 1px solid {CogPalette.SURFACE};
            }}
        """)
        top_bar.setFixedHeight(52)
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)
        top_layout.setSpacing(2)

        # 신뢰도 배지 행
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        self._confidence_badge = ConfidenceBadge(ConfidenceLevel.INFERRED)
        self._title_lbl = QLabel("No analysis yet")
        self._title_lbl.setStyleSheet(
            f"color: {CogPalette.TEXT}; font-size: 12px; font-weight: bold;"
        )
        self._save_btn = QPushButton("💾 Save to Obsidian")
        self._save_btn.setFixedHeight(24)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CogPalette.VERIFIED}22;
                color: {CogPalette.VERIFIED};
                border: 1px solid {CogPalette.VERIFIED}66;
                border-radius: 4px;
                font-size: 10px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {CogPalette.VERIFIED}44;
            }}
            QPushButton:disabled {{
                color: {CogPalette.MUTED};
                border-color: {CogPalette.SURFACE};
                background: transparent;
            }}
        """)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        badge_row.addWidget(self._confidence_badge)
        badge_row.addWidget(self._title_lbl, 1)
        badge_row.addWidget(self._save_btn)
        top_layout.addLayout(badge_row)

        # 불확실성 스펙트럼
        self._uncertainty = UncertaintyVisualizer()
        top_layout.addWidget(self._uncertainty)

        layout.addWidget(top_bar)

        # ── 메인 스플리터: 에디터 | 사이드 패널 ────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {CogPalette.SURFACE};
                width: 1px;
            }}
        """)

        # 왼쪽: Markdown 에디터
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText(
            "Analysis results will appear here...\n\n"
            "The system will extract causal structures, identification strategies,\n"
            "and mathematical primitives from your research material."
        )
        self._editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {CogPalette.BASE};
                color: {CogPalette.TEXT};
                border: none;
                font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.6;
                padding: 16px;
                selection-background-color: {CogPalette.SURFACE};
            }}
            QScrollBar:vertical {{
                background: {CogPalette.MANTLE};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {CogPalette.OVERLAY};
                border-radius: 4px;
            }}
        """)
        # 구문 강조
        self._highlighter = ContradictionHighlighter(self._editor.document())
        self._editor.textChanged.connect(self._on_text_changed)

        editor_layout.addWidget(self._editor)
        splitter.addWidget(editor_widget)

        # 오른쪽: 인지 보조 패널들 (Progressive Disclosure)
        side_panel = QWidget()
        side_panel.setFixedWidth(280)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(8, 8, 8, 8)
        side_layout.setSpacing(8)
        side_panel.setStyleSheet(f"background: {CogPalette.MANTLE};")

        # Provenance Trail
        self._provenance = ProvenanceTrail()
        side_layout.addWidget(self._provenance)

        # Equation Scaffold
        self._eq_scaffold = EquationScaffold()
        side_layout.addWidget(self._eq_scaffold)

        # Local Graph View
        self._graph_view = LocalGraphView()
        side_layout.addWidget(self._graph_view)

        # Calm Monetization (유휴 시)
        self._monetization = CalmMonetizationWidget()
        side_layout.addWidget(self._monetization)

        side_layout.addStretch()

        # 사이드 패널 스크롤
        side_scroll = QScrollArea()
        side_scroll.setWidget(side_panel)
        side_scroll.setWidgetResizable(True)
        side_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        side_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {CogPalette.MANTLE}; }}
            QScrollBar:vertical {{
                background: {CogPalette.MANTLE}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {CogPalette.OVERLAY}; border-radius: 3px;
            }}
        """)
        splitter.addWidget(side_scroll)
        splitter.setSizes([600, 280])

        layout.addWidget(splitter, 1)

    def _on_text_changed(self):
        """텍스트 변경 시 유휴 타이머 리셋."""
        self._idle_timer.start(30_000)  # 30초 후 유휴 상태
        self._monetization.set_idle(False)

    def _on_idle(self):
        """유휴 상태 진입 — 수익화 위젯 표시 허용."""
        self._monetization.set_idle(True)

    def _on_save(self):
        content = self._editor.toPlainText()
        if content.strip():
            self.save_requested.emit(content)

    def set_focus_mode(self, active: bool):
        """Focus Mode 전파."""
        self._monetization.set_focus_mode(active)

    def set_content(self, markdown: str, title: str = ""):
        """분석 결과 설정 — 모든 인지 보조 패널 자동 업데이트."""
        self._current_markdown = markdown
        self._current_title = title

        # 에디터 업데이트
        self._editor.setPlainText(markdown)
        self._save_btn.setEnabled(bool(markdown.strip()))

        # 제목 업데이트
        if title:
            self._title_lbl.setText(title[:50])

        # 신뢰도 배지 업데이트
        if '[[DML]]' in markdown or '[[IV]]' in markdown or '[[DID]]' in markdown:
            self._confidence_badge.set_level(ConfidenceLevel.VERIFIED)
        elif 'speculative' in markdown.lower() or 'hypothesize' in markdown.lower():
            self._confidence_badge.set_level(ConfidenceLevel.SPECULATIVE)
        else:
            self._confidence_badge.set_level(ConfidenceLevel.INFERRED)

        # 불확실성 분석
        self._uncertainty.analyze_markdown(markdown)

        # Provenance Trail 업데이트
        self._provenance.set_from_markdown(markdown)

        # 수식 스캐폴드 업데이트
        self._eq_scaffold.extract_from_markdown(markdown)

        # 로컬 그래프 업데이트
        self._graph_view.extract_from_markdown(title, markdown)

        # 유휴 타이머 시작
        self._idle_timer.start(60_000)  # 1분 후 유휴

    def append_stream(self, chunk: str):
        """스트리밍 청크 추가."""
        cursor = self._editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()

    def get_content(self) -> str:
        return self._editor.toPlainText()

    def clear(self):
        self._editor.clear()
        self._current_markdown = ""
        self._save_btn.setEnabled(False)
        self._title_lbl.setText("No analysis yet")
