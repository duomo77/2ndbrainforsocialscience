"""
input_panel.py  —  ROS v7.0 Universal Science Input Panel
==========================================================
전 과학 분야 지원:
  - 학문 분야 선택기 (45개 분야)
  - 에피스테믹 모드 전환 (실증/해석/비판/혼합)
  - 멀티소스 입력 탭 (논문/스크립트/데이터셋/수식/질적자료)
  - 저널명 기반 자동 분류
"""
from __future__ import annotations

import os
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QGroupBox, QTabWidget, QComboBox, QFrame,
    QScrollArea, QSizePolicy,
)


# ══════════════════════════════════════════════════════════════════════════════
# 에피스테믹 모드 정의
# ══════════════════════════════════════════════════════════════════════════════

EPISTEMIC_MODES = {
    "auto": {
        "label": "🔄 자동 감지",
        "desc": "분야와 내용에 따라 자동 선택",
        "color": "#6b7280",
    },
    "positivist": {
        "label": "📊 실증주의",
        "desc": "계량·통계·인과추론·실험 설계",
        "color": "#2563eb",
    },
    "interpretivist": {
        "label": "🔍 해석주의",
        "desc": "질적 연구·민족지·현상학·근거이론",
        "color": "#7c3aed",
    },
    "critical": {
        "label": "⚡ 비판이론",
        "desc": "담론분석·비판적 실재론·권력 분석",
        "color": "#dc2626",
    },
    "mixed": {
        "label": "🔀 혼합방법론",
        "desc": "질적+양적 통합·순차/동시 설계",
        "color": "#059669",
    },
    "computational": {
        "label": "💻 계산과학",
        "desc": "시뮬레이션·ML·네트워크·복잡계",
        "color": "#d97706",
    },
    "experimental": {
        "label": "🧪 실험과학",
        "desc": "자연과학 실험·RCT·임상시험",
        "color": "#0891b2",
    },
}

# 학문 분야 그룹 (드롭다운용)
DISCIPLINE_GROUPS = {
    "── 사회과학 ──": [
        "Economics", "Sociology", "Political Science", "Psychology",
        "Anthropology", "Communication", "Education", "Geography",
        "Criminology", "Social Work", "Demography",
    ],
    "── 자연과학 ──": [
        "Physics", "Chemistry", "Biology", "Mathematics", "Statistics",
        "Earth Science", "Environmental Science", "Astronomy",
        "Ecology", "Neuroscience", "Biochemistry",
    ],
    "── 공학/응용 ──": [
        "Computer Science", "Machine Learning / AI", "Engineering",
        "Data Science", "Operations Research", "Information Systems",
    ],
    "── 의학/보건 ──": [
        "Medicine", "Public Health", "Epidemiology",
        "Pharmacology", "Nursing", "Clinical Psychology",
    ],
    "── 인문학 ──": [
        "History", "Philosophy", "Linguistics", "Literature",
        "Cultural Studies", "Religious Studies",
    ],
    "── 학제간 ──": [
        "Interdisciplinary", "Science & Technology Studies",
        "Cognitive Science", "Complexity Science",
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# DROP ZONE
# ══════════════════════════════════════════════════════════════════════════════

class DropZone(QLabel):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("📄 PDF / TXT / CSV를 여기에 드래그하거나\n클릭하여 파일 선택")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self._set_idle_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _set_idle_style(self):
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #6b7280;
                border-radius: 8px;
                color: #9ca3af;
                font-size: 12px;
                background: #1f2937;
                padding: 12px;
            }
        """)

    def _set_hover_style(self):
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #7c3aed;
                border-radius: 8px;
                color: #c4b5fd;
                font-size: 12px;
                background: #2d1b69;
                padding: 12px;
            }
        """)

    def mousePressEvent(self, event):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "파일 선택", "",
            "지원 파일 (*.pdf *.txt *.md *.srt *.vtt *.csv *.tsv *.xlsx *.xls);;"
            "음성 파일 - 전사 필요 (*.mp3 *.wav *.m4a *.flac *.aac *.ogg *.webm);;"
            "모든 파일 (*.*)"
        )
        if path:
            self.file_dropped.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_hover_style()

    def dragLeaveEvent(self, event):
        self._set_idle_style()

    def dropEvent(self, event: QDropEvent):
        self._set_idle_style()
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.file_dropped.emit(path)


# ══════════════════════════════════════════════════════════════════════════════
# TOPIC BADGE
# ══════════════════════════════════════════════════════════════════════════════

class TopicBadge(QLabel):
    COLORS = {
        "rule":   ("#059669", "#d1fae5"),
        "keyword": ("#d97706", "#fef3c7"),
        "llm":    ("#7c3aed", "#ede9fe"),
        "manual": ("#2563eb", "#dbeafe"),
        "default": ("#6b7280", "#f3f4f6"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_empty()
        self.setMinimumWidth(120)

    def _set_empty(self):
        self.setText("미분류")
        self.setStyleSheet(
            "QLabel { background: #374151; color: #9ca3af; border-radius: 4px; "
            "padding: 3px 8px; font-size: 11px; }"
        )

    def set_topic(self, topic: str, method: str, icon: str, label: str):
        fg, bg = self.COLORS.get(method, self.COLORS["default"])
        self.setText(f"{icon} {label}")
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; color: {fg}; border-radius: 4px; "
            f"padding: 3px 8px; font-size: 11px; font-weight: bold; }}"
        )
        self.setToolTip(f"분류: {topic} (방법: {method})")

    def reset(self):
        self._set_empty()


# ══════════════════════════════════════════════════════════════════════════════
# EPISTEMIC MODE SELECTOR
# ══════════════════════════════════════════════════════════════════════════════

class EpistemicModeSelector(QWidget):
    """에피스테믹 모드 선택 위젯."""

    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = "auto"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel("인식론:")
        lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        layout.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.setStyleSheet("""
            QComboBox {
                background: #1f2937; color: #e5e7eb;
                border: 1px solid #374151; border-radius: 4px;
                padding: 3px 8px; font-size: 11px; min-width: 160px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1f2937; color: #e5e7eb;
                selection-background-color: #374151;
            }
        """)
        for key, meta in EPISTEMIC_MODES.items():
            self.combo.addItem(meta["label"], userData=key)
        self.combo.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self.combo)

        self.desc_lbl = QLabel(EPISTEMIC_MODES["auto"]["desc"])
        self.desc_lbl.setStyleSheet("color: #6b7280; font-size: 10px; font-style: italic;")
        layout.addWidget(self.desc_lbl, 1)

    def _on_changed(self, idx: int):
        key = self.combo.itemData(idx)
        if key:
            self._current = key
            self.desc_lbl.setText(EPISTEMIC_MODES[key]["desc"])
            self.mode_changed.emit(key)

    def get_mode(self) -> str:
        return self._current

    def set_mode(self, mode: str):
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == mode:
                self.combo.setCurrentIndex(i)
                break


# ══════════════════════════════════════════════════════════════════════════════
# MAIN INPUT PANEL
# ══════════════════════════════════════════════════════════════════════════════

class InputPanel(QWidget):
    """ROS v7.0 범용 과학 입력 패널."""

    analyze_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf_path = ""
        self._current_topic = "Uncategorized"
        self._current_method = ""
        self._classify_timer = QTimer()
        self._classify_timer.setSingleShot(True)
        self._classify_timer.timeout.connect(self._run_classification)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        inner_widget = QWidget()
        layout = QVBoxLayout(inner_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ── 헤더 ──────────────────────────────────────────
        header_row = QHBoxLayout()
        title_lbl = QLabel("🔬 Research Input")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title_lbl.setFont(font)
        title_lbl.setStyleSheet("color: #e5e7eb;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()
        layout.addLayout(header_row)

        # ── 학문 분야 + 에피스테믹 모드 ──────────────────
        domain_group = QGroupBox("연구 도메인")
        domain_group.setStyleSheet(self._group_style())
        domain_layout = QVBoxLayout(domain_group)
        domain_layout.setSpacing(8)
        domain_layout.setContentsMargins(10, 14, 10, 10)

        # 학문 분야 선택기
        disc_row = QHBoxLayout()
        disc_lbl = QLabel("학문 분야:")
        disc_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        disc_row.addWidget(disc_lbl)

        self.discipline_combo = QComboBox()
        self.discipline_combo.setStyleSheet("""
            QComboBox {
                background: #1f2937; color: #e5e7eb;
                border: 1px solid #374151; border-radius: 4px;
                padding: 3px 8px; font-size: 11px; min-width: 200px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1f2937; color: #e5e7eb;
                selection-background-color: #374151;
            }
        """)
        self._populate_discipline_combo()
        disc_row.addWidget(self.discipline_combo)
        disc_row.addStretch()
        domain_layout.addLayout(disc_row)

        # 에피스테믹 모드
        self.epistemic_selector = EpistemicModeSelector()
        domain_layout.addWidget(self.epistemic_selector)

        layout.addWidget(domain_group)

        # ── 메타데이터 폼 ──────────────────────────────────
        meta_group = QGroupBox("메타데이터")
        meta_group.setStyleSheet(self._group_style())
        meta_form = QFormLayout(meta_group)
        meta_form.setSpacing(8)
        meta_form.setContentsMargins(10, 14, 10, 10)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("제목 (PDF 로드 시 자동 입력)")
        self.title_edit.setStyleSheet(self._input_style())
        meta_form.addRow("제목 *", self.title_edit)

        self.authors_edit = QLineEdit()
        self.authors_edit.setPlaceholderText("저자 (쉼표 구분)")
        self.authors_edit.setStyleSheet(self._input_style())
        meta_form.addRow("저자", self.authors_edit)

        year_row = QHBoxLayout()
        self.year_edit = QLineEdit()
        self.year_edit.setPlaceholderText("2024")
        self.year_edit.setMaximumWidth(75)
        self.year_edit.setStyleSheet(self._input_style())
        self.zotero_edit = QLineEdit()
        self.zotero_edit.setPlaceholderText("zotero://select/library/items/XXXXXXXX")
        self.zotero_edit.setStyleSheet(self._input_style())
        year_row.addWidget(self.year_edit)
        year_row.addWidget(QLabel("Zotero:"))
        year_row.addWidget(self.zotero_edit)
        meta_form.addRow("연도", year_row)

        # 저널명 + 분류
        self.journal_edit = QLineEdit()
        self.journal_edit.setPlaceholderText(
            "저널명 (예: Nature, Econometrica, JMLR, Lancet, AER)"
        )
        self.journal_edit.setStyleSheet(self._input_style())
        self.journal_edit.textChanged.connect(self._on_journal_changed)
        meta_form.addRow("저널/출처", self.journal_edit)

        classify_row = QHBoxLayout()
        classify_row.addWidget(QLabel("분류:"))
        self.topic_badge = TopicBadge()
        classify_row.addWidget(self.topic_badge, 1)
        self.manual_topic_combo = QComboBox()
        self.manual_topic_combo.setFixedWidth(170)
        self.manual_topic_combo.setStyleSheet("""
            QComboBox {
                background: #1f2937; color: #e5e7eb;
                border: 1px solid #374151; border-radius: 4px;
                padding: 2px 6px; font-size: 10px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1f2937; color: #e5e7eb;
                selection-background-color: #374151;
            }
        """)
        self._populate_topic_combo()
        self.manual_topic_combo.currentTextChanged.connect(self._on_manual_topic_changed)
        classify_row.addWidget(self.manual_topic_combo)
        meta_form.addRow("", classify_row)

        layout.addWidget(meta_group)

        # ── 멀티소스 입력 탭 ──────────────────────────────
        content_group = QGroupBox("연구 자료 입력")
        content_group.setStyleSheet(self._group_style())
        content_layout = QVBoxLayout(content_group)
        content_layout.setContentsMargins(8, 12, 8, 8)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #374151; border-radius: 4px;
            }
            QTabBar::tab {
                background: #1f2937; color: #9ca3af;
                padding: 5px 10px; font-size: 10px;
                border: 1px solid #374151;
                border-bottom: none;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background: #7c3aed; color: white;
            }
            QTabBar::tab:hover:!selected { background: #374151; }
        """)

        # 1. PDF/파일 탭
        self.tab_widget.addTab(self._build_file_tab(), "📄 파일")

        # 2. 텍스트 탭 (논문 본문)
        self.tab_widget.addTab(self._build_text_tab(), "✏️ 텍스트")

        # 3. 스크립트/강의록 탭
        self.tab_widget.addTab(self._build_transcript_tab(), "🎙️ 스크립트")

        # 4. 데이터셋 탭
        self.tab_widget.addTab(self._build_dataset_tab(), "📊 데이터셋")

        # 5. 수식 탭
        self.tab_widget.addTab(self._build_equation_tab(), "📐 수식")

        # 6. 질적 자료 탭
        self.tab_widget.addTab(self._build_qualitative_tab(), "🔍 질적 자료")

        content_layout.addWidget(self.tab_widget)
        layout.addWidget(content_group)

        # ── 분석 버튼 ──────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.clear_btn = QPushButton("🗑 초기화")
        self.clear_btn.clicked.connect(self._clear_all)
        self.clear_btn.setStyleSheet(
            "QPushButton { border: 1px solid #374151; border-radius: 4px; "
            "padding: 7px 14px; color: #9ca3af; background: #1f2937; }"
            "QPushButton:hover { background: #374151; color: #e5e7eb; }"
        )

        self.analyze_btn = QPushButton("🚀 분석 시작")
        self.analyze_btn.setStyleSheet(
            "QPushButton { background: #7c3aed; color: white; border-radius: 4px; "
            "padding: 7px 22px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #6d28d9; }"
            "QPushButton:disabled { background: #4c1d95; color: #a78bfa; }"
        )
        self.analyze_btn.clicked.connect(self._request_analysis)

        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.analyze_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        scroll.setWidget(inner_widget)
        outer.addWidget(scroll)

    # ── 탭 빌더 ──────────────────────────────────────────

    def _build_file_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._on_file_dropped)
        layout.addWidget(self.drop_zone)
        self.file_status = QLabel("")
        self.file_status.setStyleSheet("color: #059669; font-size: 11px;")
        self.file_status.setWordWrap(True)
        layout.addWidget(self.file_status)
        return tab

    def _build_text_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        hint = QLabel("Abstract + Methodology + Results 구간 붙여넣기 권장")
        hint.setStyleSheet("color: #6b7280; font-size: 10px;")
        layout.addWidget(hint)
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("논문 텍스트를 여기에 붙여넣기...")
        self.text_input.setStyleSheet(self._textedit_style())
        layout.addWidget(self.text_input)
        return tab

    def _build_transcript_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        hint = QLabel("강의록, 인터뷰, 회의록, 음성 스크립트 입력 (TXT/MD 파일 또는 직접 붙여넣기)")
        hint.setStyleSheet("color: #6b7280; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("출처:"))
        self.transcript_source = QLineEdit()
        self.transcript_source.setPlaceholderText("예: 강의명, 인터뷰 대상자, 회의명")
        self.transcript_source.setStyleSheet(self._input_style())
        meta_row.addWidget(self.transcript_source)
        meta_row.addWidget(QLabel("날짜:"))
        self.transcript_date = QLineEdit()
        self.transcript_date.setPlaceholderText("2024-01-01")
        self.transcript_date.setMaximumWidth(100)
        self.transcript_date.setStyleSheet(self._input_style())
        meta_row.addWidget(self.transcript_date)
        layout.addLayout(meta_row)

        self.transcript_input = QTextEdit()
        self.transcript_input.setPlaceholderText(
            "스크립트 내용을 붙여넣기...\n\n"
            "화자 구분 형식 지원:\n"
            "  [00:00] 화자A: 내용...\n"
            "  Speaker 1: 내용..."
        )
        self.transcript_input.setStyleSheet(self._textedit_style())
        layout.addWidget(self.transcript_input)
        return tab

    def _build_dataset_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        hint = QLabel("CSV/Excel 파일 업로드 또는 데이터 구조 설명 입력")
        hint.setStyleSheet("color: #6b7280; font-size: 10px;")
        layout.addWidget(hint)

        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("데이터셋명:"))
        self.dataset_name = QLineEdit()
        self.dataset_name.setPlaceholderText("예: KLIPS 2023, NHANES, World Bank WDI")
        self.dataset_name.setStyleSheet(self._input_style())
        meta_row.addWidget(self.dataset_name)
        layout.addLayout(meta_row)

        self.dataset_drop = DropZone()
        self.dataset_drop.setText("📊 CSV / Excel 파일을 드래그하거나 클릭하여 선택")
        self.dataset_drop.file_dropped.connect(self._on_dataset_dropped)
        layout.addWidget(self.dataset_drop)

        self.dataset_status = QLabel("")
        self.dataset_status.setStyleSheet("color: #059669; font-size: 11px;")
        layout.addWidget(self.dataset_status)

        desc_lbl = QLabel("또는 데이터 구조 직접 설명:")
        desc_lbl.setStyleSheet("color: #6b7280; font-size: 10px;")
        layout.addWidget(desc_lbl)

        self.dataset_desc = QTextEdit()
        self.dataset_desc.setMaximumHeight(80)
        self.dataset_desc.setPlaceholderText(
            "변수 목록, 관측치 수, 패널 구조, 처치/결과 변수 등 설명..."
        )
        self.dataset_desc.setStyleSheet(self._textedit_style())
        layout.addWidget(self.dataset_desc)
        return tab

    def _build_equation_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        hint = QLabel("LaTeX 수식 또는 수학적 구조 입력 — 수식 온톨로지 분석 수행")
        hint.setStyleSheet("color: #6b7280; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.equation_input = QTextEdit()
        self.equation_input.setPlaceholderText(
            "수식 입력 예시:\n\n"
            "Y_i = \\alpha + \\theta D_i + X_i'\\beta + \\epsilon_i\n\n"
            "또는 수식 설명:\n"
            "DML 추정량, 직교성 조건, 점근적 정규성..."
        )
        self.equation_input.setStyleSheet(self._textedit_style())
        layout.addWidget(self.equation_input)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("수식 유형:"))
        self.eq_type_combo = QComboBox()
        self.eq_type_combo.addItems([
            "회귀/추정량", "확률 모형", "최적화", "미분방정식",
            "통계 검정", "행렬/선형대수", "기타"
        ])
        self.eq_type_combo.setStyleSheet("""
            QComboBox {
                background: #1f2937; color: #e5e7eb;
                border: 1px solid #374151; border-radius: 4px;
                padding: 2px 6px; font-size: 10px;
            }
        """)
        type_row.addWidget(self.eq_type_combo)
        type_row.addStretch()
        layout.addLayout(type_row)
        return tab

    def _build_qualitative_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        hint = QLabel("인터뷰 데이터, 현장노트, 문서 자료, 담론 텍스트 입력")
        hint.setStyleSheet("color: #6b7280; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("자료 유형:"))
        self.qual_type_combo = QComboBox()
        self.qual_type_combo.addItems([
            "심층 인터뷰", "포커스 그룹", "현장노트/민족지",
            "문서/아카이브", "담론/텍스트", "시각 자료 설명",
            "근거이론 메모", "내러티브", "기타"
        ])
        self.qual_type_combo.setStyleSheet("""
            QComboBox {
                background: #1f2937; color: #e5e7eb;
                border: 1px solid #374151; border-radius: 4px;
                padding: 2px 6px; font-size: 10px;
            }
        """)
        meta_row.addWidget(self.qual_type_combo)
        meta_row.addWidget(QLabel("분석 프레임:"))
        self.qual_framework = QLineEdit()
        self.qual_framework.setPlaceholderText("예: 근거이론, 담론분석, 현상학")
        self.qual_framework.setStyleSheet(self._input_style())
        self.qual_framework.setMaximumWidth(160)
        meta_row.addWidget(self.qual_framework)
        meta_row.addStretch()
        layout.addLayout(meta_row)

        self.qual_input = QTextEdit()
        self.qual_input.setPlaceholderText(
            "질적 자료 내용 붙여넣기...\n\n"
            "인터뷰 발췌, 현장노트, 문서 내용 등"
        )
        self.qual_input.setStyleSheet(self._textedit_style())
        layout.addWidget(self.qual_input)
        return tab

    # ── 스타일 헬퍼 ──────────────────────────────────────

    def _group_style(self) -> str:
        return """
            QGroupBox {
                border: 1px solid #374151;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 4px;
                background: #111827;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #9ca3af;
                font-size: 11px;
            }
        """

    def _input_style(self) -> str:
        return (
            "QLineEdit { background: #1f2937; color: #e5e7eb; "
            "border: 1px solid #374151; border-radius: 4px; padding: 4px 8px; "
            "font-size: 11px; }"
            "QLineEdit:focus { border-color: #7c3aed; }"
        )

    def _textedit_style(self) -> str:
        return (
            "QTextEdit { background: #1f2937; color: #e5e7eb; "
            "border: 1px solid #374151; border-radius: 4px; padding: 6px; "
            "font-size: 11px; font-family: 'Consolas', monospace; }"
            "QTextEdit:focus { border-color: #7c3aed; }"
        )

    # ── 학문 분야 콤보박스 ────────────────────────────────

    def _populate_discipline_combo(self):
        self.discipline_combo.clear()
        self.discipline_combo.addItem("General (일반)", userData="General")
        for group_label, disciplines in DISCIPLINE_GROUPS.items():
            self.discipline_combo.addItem(group_label)
            idx = self.discipline_combo.count() - 1
            item = self.discipline_combo.model().item(idx)
            if item:
                item.setEnabled(False)
                item.setForeground(__import__('PyQt6.QtGui', fromlist=['QColor']).QColor("#6b7280"))
            for disc in disciplines:
                self.discipline_combo.addItem(f"  {disc}", userData=disc)

    def get_discipline(self) -> str:
        data = self.discipline_combo.currentData()
        return data if data else "General"

    # ── 주제 콤보박스 ─────────────────────────────────────

    def _populate_topic_combo(self):
        try:
            from core.classifier import TOPIC_META
        except Exception:
            TOPIC_META = {}
        self.manual_topic_combo.blockSignals(True)
        self.manual_topic_combo.clear()
        self.manual_topic_combo.addItem("── 수동 변경 ──")
        for folder, meta in TOPIC_META.items():
            self.manual_topic_combo.addItem(
                f"{meta.get('icon','📂')} {folder}", userData=folder
            )
        self.manual_topic_combo.blockSignals(False)

    # ── 저널 분류 ─────────────────────────────────────────

    def _on_journal_changed(self, text: str):
        if text.strip():
            self._classify_timer.start(500)
        else:
            self.topic_badge.reset()
            self._current_topic = "Uncategorized"

    def _run_classification(self):
        journal = self.journal_edit.text().strip()
        title = self.title_edit.text().strip()
        if not journal:
            return
        try:
            from core.classifier import classify_by_journal, TOPIC_META
            from core.config import load_config
            cfg = load_config()
            custom_rules = cfg.get("classification_rules", {})
            topic, method = classify_by_journal(journal, title, custom_rules)
            self._current_topic = topic
            self._current_method = method
            meta = TOPIC_META.get(topic, {"icon": "📂", "label": topic})
            self.topic_badge.set_topic(topic, method, meta.get("icon","📂"), meta.get("label", topic))
            self.manual_topic_combo.blockSignals(True)
            for i in range(self.manual_topic_combo.count()):
                if self.manual_topic_combo.itemData(i) == topic:
                    self.manual_topic_combo.setCurrentIndex(i)
                    break
            self.manual_topic_combo.blockSignals(False)
        except Exception:
            pass

    def _on_manual_topic_changed(self, text: str):
        try:
            from core.classifier import TOPIC_META
        except Exception:
            TOPIC_META = {}
        topic = self.manual_topic_combo.currentData()
        if not topic:
            return
        self._current_topic = topic
        self._current_method = "manual"
        meta = TOPIC_META.get(topic, {"icon": "📂", "label": topic})
        self.topic_badge.set_topic(topic, "manual", meta.get("icon","📂"), meta.get("label", topic))

    # ── 파일 처리 ─────────────────────────────────────────

    def _on_file_dropped(self, path: str):
        self._pdf_path = path
        ext = os.path.splitext(path)[1].lower()
        filename = os.path.basename(path)
        self.file_status.setText(f"✅ 로드됨: {filename}")
        if ext == ".pdf":
            try:
                from core.pdf_parser import get_pdf_metadata
                meta = get_pdf_metadata(path)
                if meta.get("title") and not self.title_edit.text():
                    self.title_edit.setText(meta["title"])
                if meta.get("author") and not self.authors_edit.text():
                    self.authors_edit.setText(meta["author"])
            except Exception:
                pass
        elif ext in (".csv", ".tsv", ".xlsx", ".xls"):
            self.tab_widget.setCurrentIndex(3)  # 데이터셋 탭
            self.dataset_status.setText(f"✅ 데이터셋 로드됨: {filename}")

    def _on_dataset_dropped(self, path: str):
        self._pdf_path = path
        filename = os.path.basename(path)
        self.dataset_status.setText(f"✅ 데이터셋 로드됨: {filename}")
        if not self.dataset_name.text():
            self.dataset_name.setText(os.path.splitext(filename)[0])

    # ── 초기화 ───────────────────────────────────────────

    def _clear_all(self):
        self._pdf_path = ""
        self._current_topic = "Uncategorized"
        self.title_edit.clear()
        self.authors_edit.clear()
        self.year_edit.clear()
        self.zotero_edit.clear()
        self.journal_edit.clear()
        self.text_input.clear()
        self.transcript_input.clear()
        self.transcript_source.clear()
        self.transcript_date.clear()
        self.dataset_desc.clear()
        self.dataset_name.clear()
        self.equation_input.clear()
        self.qual_input.clear()
        self.qual_framework.clear()
        self.file_status.setText("")
        self.dataset_status.setText("")
        self.topic_badge.reset()
        self.drop_zone.setText("📄 PDF / TXT / CSV를 여기에 드래그하거나\n클릭하여 파일 선택")
        self.manual_topic_combo.setCurrentIndex(0)
        self.discipline_combo.setCurrentIndex(0)
        self.epistemic_selector.set_mode("auto")

    # ── 분석 요청 ─────────────────────────────────────────

    def _request_analysis(self):
        from PyQt6.QtWidgets import QMessageBox

        title = self.title_edit.text().strip()
        tab_idx = self.tab_widget.currentIndex()

        # 탭별 입력 타입 및 콘텐츠 결정
        tab_map = {
            0: "paper",
            1: "paper",
            2: "transcript",
            3: "dataset",
            4: "equation",
            5: "qualitative",
        }
        input_type = tab_map.get(tab_idx, "paper")

        content = ""
        extra = {}

        if tab_idx == 0:  # 파일 탭
            if not self._pdf_path:
                QMessageBox.warning(self, "입력 오류", "파일을 업로드해주세요.")
                return
            ext = os.path.splitext(self._pdf_path)[1].lower()
            if ext == ".pdf":
                try:
                    from core.pdf_parser import extract_text_from_pdf
                    content = extract_text_from_pdf(self._pdf_path)
                except Exception as e:
                    QMessageBox.critical(self, "파일 오류", str(e))
                    return
            elif ext in (".csv", ".tsv", ".xlsx", ".xls"):
                input_type = "dataset"
                content = f"[데이터셋 파일: {os.path.basename(self._pdf_path)}]"
                extra["file_path"] = self._pdf_path
                extra["dataset_name"] = self.dataset_name.text().strip() or os.path.basename(self._pdf_path)
            elif ext in (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".webm"):
                QMessageBox.warning(
                    self,
                    "전사 필요",
                    "음성 파일은 먼저 .txt, .md, .srt, .vtt로 전사한 뒤 분석해주세요.",
                )
                return
            else:
                try:
                    with open(self._pdf_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception as e:
                    QMessageBox.critical(self, "파일 오류", str(e))
                    return

        elif tab_idx == 1:  # 텍스트 탭
            content = self.text_input.toPlainText().strip()

        elif tab_idx == 2:  # 스크립트 탭
            content = self.transcript_input.toPlainText().strip()
            extra["source_name"] = self.transcript_source.text().strip()
            extra["date"] = self.transcript_date.text().strip()
            if not title:
                title = self.transcript_source.text().strip() or "Transcript"

        elif tab_idx == 3:  # 데이터셋 탭
            if self._pdf_path and os.path.splitext(self._pdf_path)[1].lower() in (".csv", ".tsv", ".xlsx", ".xls"):
                content = f"[데이터셋 파일: {os.path.basename(self._pdf_path)}]"
                extra["file_path"] = self._pdf_path
            else:
                content = self.dataset_desc.toPlainText().strip()
            extra["dataset_name"] = self.dataset_name.text().strip()
            if not title:
                title = extra.get("dataset_name", "Dataset Analysis")

        elif tab_idx == 4:  # 수식 탭
            content = self.equation_input.toPlainText().strip()
            extra["material_type"] = self.eq_type_combo.currentText()
            if not title:
                title = "Equation Analysis"

        elif tab_idx == 5:  # 질적 자료 탭
            content = self.qual_input.toPlainText().strip()
            extra["material_type"] = self.qual_type_combo.currentText()
            extra["framework"] = self.qual_framework.text().strip()
            if not title:
                title = "Qualitative Analysis"

        if not content:
            QMessageBox.warning(self, "입력 오류", "분석할 내용을 입력해주세요.")
            return

        if not title:
            QMessageBox.warning(self, "입력 오류", "제목을 입력해주세요.")
            return

        payload = {
            "input_type": input_type,
            "title": title,
            "authors": self.authors_edit.text().strip(),
            "year": self.year_edit.text().strip(),
            "zotero_link": self.zotero_edit.text().strip(),
            "journal": self.journal_edit.text().strip(),
            "topic": self._current_topic,
            "topic_method": self._current_method,
            "discipline": self.get_discipline(),
            "epistemic_mode": self.epistemic_selector.get_mode(),
            "content": content,
            **extra,
        }
        self.analyze_requested.emit(payload)

    def set_analyzing(self, is_analyzing: bool):
        self.analyze_btn.setEnabled(not is_analyzing)
        self.analyze_btn.setText("⏳ 분석 중..." if is_analyzing else "🚀 분석 시작")
