"""
main_window.py — ROS Main Window (Research Operating System)
=============================================================
모던 다크 테마 · 멀티탭 입력 · 실시간 스트리밍 · Obsidian 자동 동기화
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QLabel, QPushButton, QTextEdit, QLineEdit,
    QFileDialog, QComboBox, QCheckBox, QStatusBar, QFrame,
    QScrollArea, QGroupBox, QProgressBar, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QApplication, QToolBar,
)
from PyQt6.QtCore import Qt, QSize, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPalette, QAction

from core import obsidian_sync, memory
from core.worker import AnalysisWorker, ValidationWorker
from core.config import Config
from ui.settings_dialog import PRESET_MODELS, SettingsDialog
from ui.infra_dashboard import InfraDashboard

# v6.0 인지 UX 컴포넌트 (지연 임포트로 안전 처리)
try:
    from ui.cognitive_panels import (
        SemanticBreadcrumb, ContradictionHighlighter,
        LocalGraphView, EquationScaffold,
    )
    from ui.cognitive_ux import (
        CalmMonetizationWidget, ConfidenceBadge, ConfidenceLevel,
        UncertaintyVisualizer, ProvenanceTrail,
    )
    _COG_UX_AVAILABLE = True
except Exception:
    _COG_UX_AVAILABLE = False


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    c = {
        "bg":      QColor("#1e1e2e"),
        "surface": QColor("#2a2a3e"),
        "panel":   QColor("#252535"),
        "border":  QColor("#3d3d5c"),
        "text":    QColor("#cdd6f4"),
        "subtext": QColor("#a6adc8"),
        "accent":  QColor("#89b4fa"),
        "green":   QColor("#a6e3a1"),
        "red":     QColor("#f38ba8"),
        "yellow":  QColor("#f9e2af"),
        "mauve":   QColor("#cba6f7"),
    }
    palette.setColor(QPalette.ColorRole.Window,          c["bg"])
    palette.setColor(QPalette.ColorRole.WindowText,      c["text"])
    palette.setColor(QPalette.ColorRole.Base,            c["surface"])
    palette.setColor(QPalette.ColorRole.AlternateBase,   c["panel"])
    palette.setColor(QPalette.ColorRole.Text,            c["text"])
    palette.setColor(QPalette.ColorRole.Button,          c["surface"])
    palette.setColor(QPalette.ColorRole.ButtonText,      c["text"])
    palette.setColor(QPalette.ColorRole.Link,            c["accent"])
    palette.setColor(QPalette.ColorRole.Highlight,       c["accent"])
    palette.setColor(QPalette.ColorRole.HighlightedText, c["bg"])
    app.setPalette(palette)
    app.setStyleSheet("""
        QMainWindow,QDialog{background:#1e1e2e;}
        QTabWidget::pane{border:1px solid #3d3d5c;background:#252535;border-radius:6px;}
        QTabBar::tab{background:#2a2a3e;color:#a6adc8;padding:8px 18px;border:1px solid #3d3d5c;border-bottom:none;border-radius:4px 4px 0 0;margin-right:2px;font-size:12px;}
        QTabBar::tab:selected{background:#313244;color:#cdd6f4;border-bottom:2px solid #89b4fa;}
        QTabBar::tab:hover{background:#313244;color:#cdd6f4;}
        QPushButton{background:#313244;color:#cdd6f4;border:1px solid #3d3d5c;border-radius:6px;padding:7px 16px;font-size:12px;}
        QPushButton:hover{background:#3d3d5c;border-color:#89b4fa;}
        QPushButton#primary{background:#89b4fa;color:#1e1e2e;font-weight:bold;border:none;}
        QPushButton#primary:hover{background:#b4d0fb;}
        QPushButton#danger{background:#f38ba8;color:#1e1e2e;border:none;}
        QPushButton#success{background:#a6e3a1;color:#1e1e2e;border:none;}
        QLineEdit,QTextEdit,QComboBox{background:#2a2a3e;color:#cdd6f4;border:1px solid #3d3d5c;border-radius:5px;padding:5px 8px;font-size:12px;}
        QLineEdit:focus,QTextEdit:focus{border-color:#89b4fa;}
        QGroupBox{color:#89b4fa;border:1px solid #3d3d5c;border-radius:6px;margin-top:12px;padding-top:8px;font-weight:bold;}
        QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}
        QLabel{color:#cdd6f4;}
        QSplitter::handle{background:#3d3d5c;width:2px;}
        QScrollBar:vertical{background:#1e1e2e;width:8px;}
        QScrollBar::handle:vertical{background:#3d3d5c;border-radius:4px;min-height:20px;}
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        QTreeWidget{background:#252535;color:#cdd6f4;border:1px solid #3d3d5c;border-radius:5px;}
        QTreeWidget::item:hover{background:#313244;}
        QTreeWidget::item:selected{background:#45475a;color:#89b4fa;}
        QStatusBar{background:#181825;color:#a6adc8;border-top:1px solid #3d3d5c;}
        QProgressBar{background:#2a2a3e;border:1px solid #3d3d5c;border-radius:4px;text-align:center;color:#cdd6f4;height:6px;}
        QProgressBar::chunk{background:#89b4fa;border-radius:4px;}
        QToolBar{background:#181825;border-bottom:1px solid #3d3d5c;spacing:4px;padding:4px;}
        QCheckBox{color:#cdd6f4;spacing:6px;}
        QCheckBox::indicator{width:16px;height:16px;border:1px solid #3d3d5c;border-radius:3px;background:#2a2a3e;}
        QCheckBox::indicator:checked{background:#89b4fa;border-color:#89b4fa;}
        QMenu{background:#252535;color:#cdd6f4;border:1px solid #3d3d5c;}
        QMenu::item:selected{background:#313244;}
        QMenuBar{background:#181825;color:#cdd6f4;}
        QMenuBar::item:selected{background:#313244;}
    """)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config  = Config()
        self._worker = None
        self._result = ""
        self._saved_path  = ""
        self._saved_topic = ""
        self._paper_file      = ""
        self._transcript_file = ""
        self._dataset_file    = ""
        self._notes_file      = ""

        self.setWindowTitle("🧠 Research Operating System")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._load_state()
        self._setup_cog_ux()  # v6.0 인지 UX 초기화

        if not self.config.get("api_key"):
            self._open_settings()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8,8,8,8)
        root.setSpacing(0)

        # ── v6.0 Semantic Breadcrumb ────────────────────────────────────────
        if _COG_UX_AVAILABLE:
            self._breadcrumb = SemanticBreadcrumb()
            self._breadcrumb.set_path(["Research OS", "Home"])
            root.addWidget(self._breadcrumb)

        # ── 메인 스플리터 (입력 | 결과 | 볼트) ────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_result_panel())
        splitter.addWidget(self._build_vault_panel())
        splitter.setSizes([400,700,300])
        root.addWidget(splitter, 1)

        # ── v4.0 인프라 대시보드 (접이식) ──────────────────────────────────
        self._dash_visible = False
        self._dash_toggle_btn = QPushButton("⚡ v4.0 Infrastructure Monitor  ▼")
        self._dash_toggle_btn.setStyleSheet(
            "QPushButton{background:#181825;color:#585b70;border:none;"
            "border-top:1px solid #3d3d5c;padding:4px 12px;font-size:10px;text-align:left;}"
            "QPushButton:hover{color:#89b4fa;}"
        )
        self._dash_toggle_btn.setFixedHeight(24)
        self._dash_toggle_btn.clicked.connect(self._toggle_dashboard)
        root.addWidget(self._dash_toggle_btn)

        self._infra_dashboard = InfraDashboard()
        self._infra_dashboard.setFixedHeight(260)
        self._infra_dashboard.setVisible(False)
        root.addWidget(self._infra_dashboard)

        # ── v6.0 인지 안전 수익화 (유휴 상태 전용) ──────────────────────────
        if _COG_UX_AVAILABLE:
            self._calm_monetization = CalmMonetizationWidget()
            self._calm_monetization.setVisible(False)  # 초기에는 숨김
            root.addWidget(self._calm_monetization)
            # 유휴 타이머 (2분 후 수익화 위젯 표시)
            from PyQt6.QtCore import QTimer
            self._idle_timer = QTimer(self)
            self._idle_timer.setSingleShot(True)
            self._idle_timer.timeout.connect(self._on_idle_state)
            self._idle_timer.start(120_000)

    # ── 입력 패널 ──────────────────────────────────────────────────────────────
    def _build_input_panel(self):
        w = QWidget(); w.setMinimumWidth(360); w.setMaximumWidth(480)
        l = QVBoxLayout(w); l.setContentsMargins(4,4,4,4); l.setSpacing(8)
        hdr = QLabel("📥 Input Source")
        hdr.setFont(QFont("Segoe UI",13,QFont.Weight.Bold))
        hdr.setStyleSheet("color:#89b4fa;padding:4px 0;")
        l.addWidget(hdr)
        self.input_tabs = QTabWidget()
        self.input_tabs.addTab(self._build_paper_tab(),      "📄 Paper")
        self.input_tabs.addTab(self._build_transcript_tab(), "🎙 Script")
        self.input_tabs.addTab(self._build_dataset_tab(),    "🗃 Dataset")
        self.input_tabs.addTab(self._build_equation_tab(),   "∑ Equation")
        self.input_tabs.addTab(self._build_notes_tab(),      "📋 Notes")
        l.addWidget(self.input_tabs)
        opt_box = QGroupBox("⚙️ Options")
        ol = QVBoxLayout(opt_box)
        mr = QHBoxLayout(); mr.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(PRESET_MODELS)
        mr.addWidget(self.model_combo,1); ol.addLayout(mr)
        self.auto_save_chk = QCheckBox("✅ 분석 완료 시 Obsidian 자동 저장")
        self.auto_save_chk.setChecked(self.config.get("auto_save",True))
        ol.addWidget(self.auto_save_chk)
        l.addWidget(opt_box)
        self.analyze_btn = QPushButton("🚀  분석 시작  (ROS)")
        self.analyze_btn.setObjectName("primary")
        self.analyze_btn.setMinimumHeight(44)
        self.analyze_btn.setFont(QFont("Segoe UI",12,QFont.Weight.Bold))
        self.analyze_btn.clicked.connect(self._start_analysis)
        l.addWidget(self.analyze_btn)
        self.progress = QProgressBar(); self.progress.setRange(0,0)
        self.progress.setVisible(False); self.progress.setFixedHeight(6)
        l.addWidget(self.progress)
        recent_box = QGroupBox("🕐 최근 분석")
        rl = QVBoxLayout(recent_box)
        self.recent_list = QTreeWidget(); self.recent_list.setHeaderHidden(True)
        self.recent_list.setMaximumHeight(100); self.recent_list.setRootIsDecorated(False)
        rl.addWidget(self.recent_list); l.addWidget(recent_box)
        self._refresh_recent()
        return w

    def _build_paper_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(5)
        def row(lbl, widget):
            r = QHBoxLayout(); lb = QLabel(lbl)
            lb.setFixedWidth(55); lb.setStyleSheet("color:#a6adc8;font-size:11px;")
            r.addWidget(lb); r.addWidget(widget,1); l.addLayout(r)
        self.p_title   = QLineEdit(); self.p_title.setPlaceholderText("논문 제목 *")
        self.p_authors = QLineEdit(); self.p_authors.setPlaceholderText("저자")
        self.p_year    = QLineEdit(); self.p_year.setPlaceholderText("연도")
        self.p_journal = QLineEdit(); self.p_journal.setPlaceholderText("저널명")
        self.p_zotero  = QLineEdit(); self.p_zotero.setPlaceholderText("Zotero 링크")
        row("제목", self.p_title); row("저자", self.p_authors)
        row("연도", self.p_year);  row("저널", self.p_journal); row("Zotero", self.p_zotero)
        tr = QHBoxLayout(); tr.addWidget(QLabel("주제:"))
        self.p_topic = QComboBox()
        self.p_topic.addItems(["(자동 감지)","Econometrics","MachineLearning","GeneralEconomics",
            "LaborEconomics","Finance","HealthEconomics","PublicEconomics",
            "DevelopmentEconomics","IndustrialOrganization","Statistics","WorkingPapers","Uncategorized"])
        tr.addWidget(self.p_topic,1); l.addLayout(tr)
        self.p_file_label = QLabel("📎 파일 없음")
        self.p_file_label.setStyleSheet("color:#a6adc8;font-size:11px;")
        fb = QPushButton("📂 PDF / TXT 선택"); fb.clicked.connect(lambda: self._pick_file("paper"))
        l.addWidget(fb); l.addWidget(self.p_file_label)
        l.addWidget(QLabel("또는 텍스트 직접 입력:"))
        self.p_text = QTextEdit(); self.p_text.setPlaceholderText("Abstract, Methodology, Results...")
        self.p_text.setMinimumHeight(100); l.addWidget(self.p_text)
        return w

    def _build_transcript_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(5)
        tr = QHBoxLayout(); tr.addWidget(QLabel("유형:"))
        self.t_type = QComboBox()
        self.t_type.addItems(["transcript","lecture","meeting","seminar","podcast"])
        tr.addWidget(self.t_type,1); l.addLayout(tr)
        self.t_title = QLineEdit(); self.t_title.setPlaceholderText("소스 이름 / 제목 *")
        self.t_date  = QLineEdit(); self.t_date.setPlaceholderText("날짜 (YYYY-MM-DD)")
        self.t_ctx   = QLineEdit(); self.t_ctx.setPlaceholderText("맥락 (강의명, 발표자 등)")
        l.addWidget(self.t_title); l.addWidget(self.t_date); l.addWidget(self.t_ctx)
        self.t_file_label = QLabel("📎 파일 없음")
        self.t_file_label.setStyleSheet("color:#a6adc8;font-size:11px;")
        fb = QPushButton("📂 스크립트 파일 선택 (.txt / .md)")
        fb.clicked.connect(lambda: self._pick_file("transcript"))
        l.addWidget(fb); l.addWidget(self.t_file_label)
        l.addWidget(QLabel("또는 텍스트 직접 입력:"))
        self.t_text = QTextEdit()
        self.t_text.setPlaceholderText("강의 스크립트, 회의록, 음성 변환 텍스트...")
        self.t_text.setMinimumHeight(120); l.addWidget(self.t_text)
        return w

    def _build_dataset_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(5)
        self.d_name = QLineEdit(); self.d_name.setPlaceholderText("데이터셋 이름 *")
        self.d_ctx  = QLineEdit(); self.d_ctx.setPlaceholderText("연구 맥락 / 분석 목적")
        l.addWidget(self.d_name); l.addWidget(self.d_ctx)
        self.d_file_label = QLabel("📎 파일 없음")
        self.d_file_label.setStyleSheet("color:#a6adc8;font-size:11px;")
        fb = QPushButton("📂 CSV / Excel 선택"); fb.clicked.connect(lambda: self._pick_file("dataset"))
        l.addWidget(fb); l.addWidget(self.d_file_label)
        l.addWidget(QLabel("또는 데이터 설명 입력:"))
        self.d_text = QTextEdit()
        self.d_text.setPlaceholderText("변수 설명, 데이터 구조, 출처, 패널 정보...")
        self.d_text.setMinimumHeight(140); l.addWidget(self.d_text)
        return w

    def _build_equation_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(5)
        self.eq_ctx = QLineEdit(); self.eq_ctx.setPlaceholderText("맥락 (어떤 추정량/이론?)")
        l.addWidget(self.eq_ctx)
        l.addWidget(QLabel("수식 / 이론 입력 (LaTeX 가능):"))
        self.eq_text = QTextEdit()
        self.eq_text.setPlaceholderText("예: \\theta = E[Y(1) - Y(0)]\n\nDML orthogonality:\nE[\\psi(W; \\theta_0, \\eta_0)] = 0")
        self.eq_text.setMinimumHeight(200); l.addWidget(self.eq_text)
        return w

    def _build_notes_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(5)
        self.n_title = QLineEdit(); self.n_title.setPlaceholderText("노트 제목 *")
        self.n_ctx   = QLineEdit(); self.n_ctx.setPlaceholderText("맥락 / 태그")
        l.addWidget(self.n_title); l.addWidget(self.n_ctx)
        self.n_file_label = QLabel("📎 파일 없음")
        self.n_file_label.setStyleSheet("color:#a6adc8;font-size:11px;")
        fb = QPushButton("📂 파일 선택"); fb.clicked.connect(lambda: self._pick_file("notes"))
        l.addWidget(fb); l.addWidget(self.n_file_label)
        l.addWidget(QLabel("또는 텍스트 입력:"))
        self.n_text = QTextEdit()
        self.n_text.setPlaceholderText("연구 메모, 아이디어, 읽기 노트...")
        self.n_text.setMinimumHeight(160); l.addWidget(self.n_text)
        return w

    # ── 결과 패널 ──────────────────────────────────────────────────────────────
    def _build_result_panel(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(4,4,4,4); l.setSpacing(6)
        hr = QHBoxLayout()
        hdr = QLabel("📝 Generated Wiki Note")
        hdr.setFont(QFont("Segoe UI",13,QFont.Weight.Bold))
        hdr.setStyleSheet("color:#89b4fa;")
        hr.addWidget(hdr); hr.addStretch()
        self.topic_badge = QLabel("")
        self.topic_badge.setStyleSheet("background:#313244;color:#f9e2af;border-radius:4px;padding:2px 10px;font-size:11px;")
        hr.addWidget(self.topic_badge)
        self.token_count = QLabel("0 words")
        self.token_count.setStyleSheet("color:#585b70;font-size:11px;")
        hr.addWidget(self.token_count); l.addLayout(hr)
        self.result_editor = QTextEdit()
        self.result_editor.setFont(QFont("Consolas",11))
        self.result_editor.setPlaceholderText(
            "분석 결과가 여기에 실시간으로 스트리밍됩니다...\n\n"
            "왼쪽 패널에서 입력 후 🚀 분석 시작 버튼을 클릭하세요."
        )
        # v6.0 구문 강조 (ContradictionHighlighter)
        if _COG_UX_AVAILABLE:
            self._contra_hl = ContradictionHighlighter(self.result_editor.document())
            self.result_editor.textChanged.connect(self._on_result_text_changed)
        l.addWidget(self.result_editor,1)

        # v6.0 인지 보조 패널 (수식 스캐폴드 + 로컬 그래프)
        if _COG_UX_AVAILABLE:
            cog_splitter = QSplitter(Qt.Orientation.Horizontal)
            cog_splitter.setFixedHeight(180)
            self._eq_scaffold = EquationScaffold()
            self._local_graph = LocalGraphView()
            cog_splitter.addWidget(self._eq_scaffold)
            cog_splitter.addWidget(self._local_graph)
            cog_splitter.setSizes([300, 300])
            l.addWidget(cog_splitter)
        sr = QHBoxLayout()
        self.save_btn = QPushButton("💾  Obsidian에 저장")
        self.save_btn.setObjectName("success"); self.save_btn.setMinimumHeight(38)
        self.save_btn.clicked.connect(self._manual_save); self.save_btn.setEnabled(False)
        sr.addWidget(self.save_btn,2)
        self.open_btn = QPushButton("🔗 Obsidian 열기")
        self.open_btn.setMinimumHeight(38); self.open_btn.clicked.connect(self._open_obsidian)
        self.open_btn.setEnabled(False); sr.addWidget(self.open_btn,1)
        self.copy_btn = QPushButton("📋 복사")
        self.copy_btn.setMinimumHeight(38); self.copy_btn.clicked.connect(self._copy_result)
        sr.addWidget(self.copy_btn,1)
        self.clear_btn = QPushButton("🗑 초기화")
        self.clear_btn.setObjectName("danger"); self.clear_btn.setMinimumHeight(38)
        self.clear_btn.clicked.connect(self._clear_result); sr.addWidget(self.clear_btn,1)
        l.addLayout(sr)
        return w

    # ── v6.0 인지 UX 초기화 ────────────────────────────────────────────────
    def _setup_cog_ux(self):
        """v6.0 인지 UX 컴포넌트 초기화 (안전 폴백 포함)."""
        if not _COG_UX_AVAILABLE:
            return
        # 신뢰도 배지를 상태바에 추가
        try:
            self._conf_badge = ConfidenceBadge(ConfidenceLevel.INFERRED)
            self.statusBar().addPermanentWidget(self._conf_badge)
        except Exception:
            pass

    def _on_result_text_changed(self):
        """결과 텍스트 변경 시 인지 보조 패널 업데이트."""
        if not _COG_UX_AVAILABLE:
            return
        # 유휴 타이머 리셋
        if hasattr(self, '_idle_timer'):
            self._idle_timer.start(120_000)
        if hasattr(self, '_calm_monetization'):
            self._calm_monetization.set_idle(False)
            self._calm_monetization.setVisible(False)

    def _on_idle_state(self):
        """유휴 상태 — 인지 안전 수익화 위젯 표시."""
        if _COG_UX_AVAILABLE and hasattr(self, '_calm_monetization'):
            self._calm_monetization.set_idle(True)
            self._calm_monetization.setVisible(True)

    def _update_cog_panels(self, markdown: str, title: str = ""):
        """분석 완료 후 인지 보조 패널 일괄 업데이트."""
        if not _COG_UX_AVAILABLE:
            return
        # 브레드크럼 업데이트
        if hasattr(self, '_breadcrumb'):
            topic = self._saved_topic or "Uncategorized"
            self._breadcrumb.set_path(["Research OS", "Papers", topic, title[:30]])
        # 수식 스캐폴드 업데이트
        if hasattr(self, '_eq_scaffold'):
            self._eq_scaffold.extract_from_markdown(markdown)
        # 로컬 그래프 업데이트
        if hasattr(self, '_local_graph'):
            self._local_graph.extract_from_markdown(title, markdown)
        # 신뢰도 배지 업데이트
        if hasattr(self, '_conf_badge'):
            if any(tag in markdown for tag in ['[[DML]]','[[IV]]','[[DID]]','[[RDD]]']):
                self._conf_badge.set_level(ConfidenceLevel.VERIFIED)
            elif 'speculative' in markdown.lower():
                self._conf_badge.set_level(ConfidenceLevel.SPECULATIVE)
            else:
                self._conf_badge.set_level(ConfidenceLevel.INFERRED)

    # ── 볼트 탐색기 ────────────────────────────────────────────────────────────
    def _build_vault_panel(self):
        w = QWidget(); w.setMinimumWidth(260); w.setMaximumWidth(380)
        l = QVBoxLayout(w); l.setContentsMargins(4,4,4,4); l.setSpacing(6)
        hdr = QLabel("🗂 Vault Explorer")
        hdr.setFont(QFont("Segoe UI",13,QFont.Weight.Bold))
        hdr.setStyleSheet("color:#89b4fa;padding:4px 0;")
        l.addWidget(hdr)
        self.vault_label = QLabel("볼트 미설정")
        self.vault_label.setStyleSheet("color:#585b70;font-size:10px;")
        self.vault_label.setWordWrap(True); l.addWidget(self.vault_label)
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#a6adc8;font-size:11px;")
        l.addWidget(self.stats_label)
        self.vault_tree = QTreeWidget()
        self.vault_tree.setHeaderLabels(["노트","날짜"])
        self.vault_tree.setColumnWidth(0,180)
        self.vault_tree.itemDoubleClicked.connect(self._open_note_from_tree)
        l.addWidget(self.vault_tree,1)
        br = QHBoxLayout()
        rb = QPushButton("🔄"); rb.setFixedSize(36,36); rb.setToolTip("새로고침")
        rb.clicked.connect(self._refresh_vault); br.addWidget(rb)
        ib = QPushButton("📑 인덱스 갱신"); ib.clicked.connect(self._rebuild_index)
        br.addWidget(ib,1); l.addLayout(br)
        self.graph_stats = QLabel("")
        self.graph_stats.setStyleSheet("color:#585b70;font-size:10px;border-top:1px solid #3d3d5c;padding-top:4px;")
        self.graph_stats.setWordWrap(True); l.addWidget(self.graph_stats)
        return w

    # ── 메뉴 ───────────────────────────────────────────────────────────────────
    def _add_menu_action(self, menu, text, slot, shortcut=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        self._add_menu_action(fm, "⚙️  설정", self._open_settings, "Ctrl+,")
        fm.addSeparator(); self._add_menu_action(fm, "🚪  종료", self.close, "Ctrl+Q")
        vm = mb.addMenu("Vault")
        self._add_menu_action(vm, "🔄  새로고침", self._refresh_vault, "Ctrl+R")
        self._add_menu_action(vm, "📑  인덱스 재생성", self._rebuild_index)
        self._add_menu_action(vm, "🔍  개념 스캔", self._scan_concepts)
        pm = mb.addMenu("Profile")
        self._add_menu_action(pm, "👤  연구자 프로필", self._open_profile)
        self._add_menu_action(pm, "📊  지식 그래프 통계", self._show_graph_stats)
        hm = mb.addMenu("Help")
        self._add_menu_action(hm, "📖  사용 방법", self._show_help)
        self._add_menu_action(hm, "ℹ️  About ROS", self._show_about)

    def _build_toolbar(self):
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        a1 = QAction("🚀 분석", self); a1.triggered.connect(self._start_analysis); tb.addAction(a1)
        tb.addSeparator()
        a2 = QAction("⚙️ 설정", self); a2.triggered.connect(self._open_settings); tb.addAction(a2)
        a3 = QAction("👤 프로필", self); a3.triggered.connect(self._open_profile); tb.addAction(a3)
        tb.addSeparator()
        a4 = QAction("🔄 볼트", self); a4.triggered.connect(self._refresh_vault); tb.addAction(a4)

    def _build_statusbar(self):
        sb = QStatusBar(); self.setStatusBar(sb)
        self.status_label = QLabel("Ready · Research Operating System")
        sb.addWidget(self.status_label,1)
        self.model_status = QLabel("")
        self.model_status.setStyleSheet("color:#585b70;font-size:10px;")
        sb.addPermanentWidget(self.model_status)

    def _load_state(self):
        vault = self.config.get("vault_path","")
        if vault:
            self.vault_label.setText(f"📁 {vault}")
            self._refresh_vault()
        model = self.config.get("model","gpt-4o-mini")
        idx = self.model_combo.findText(model)
        if idx >= 0: self.model_combo.setCurrentIndex(idx)
        self.model_status.setText(f"Model: {model}")
        self._update_graph_stats()

    # ── 파일 선택 ──────────────────────────────────────────────────────────────
    def _pick_file(self, tab):
        filters = {
            "paper":      "Papers (*.pdf *.txt *.md *.tex);;All Files (*)",
            "transcript": "Scripts (*.txt *.md *.srt *.vtt);;Audio (transcription required) (*.mp3 *.wav *.m4a *.flac *.aac *.ogg *.webm);;All Files (*)",
            "dataset":    "Datasets (*.csv *.xlsx *.xls *.tsv);;All Files (*)",
            "notes":      "Notes (*.txt *.md *.rst);;All Files (*)",
        }
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", filters.get(tab,"All Files (*)"))
        if not path: return
        name = Path(path).name
        if tab == "paper":
            self._paper_file = path; self.p_file_label.setText(f"📎 {name}")
            if path.endswith(".pdf"):
                from core.parsers import parse_pdf
                _, meta = parse_pdf(path, max_chars=100)
                if meta.get("title") and not self.p_title.text(): self.p_title.setText(meta["title"])
                if meta.get("author") and not self.p_authors.text(): self.p_authors.setText(meta["author"])
        elif tab == "transcript":
            self._transcript_file = path; self.t_file_label.setText(f"📎 {name}")
            if not self.t_title.text(): self.t_title.setText(Path(path).stem)
        elif tab == "dataset":
            self._dataset_file = path; self.d_file_label.setText(f"📎 {name}")
            if not self.d_name.text(): self.d_name.setText(Path(path).stem)
        elif tab == "notes":
            self._notes_file = path; self.n_file_label.setText(f"📎 {name}")
            if not self.n_title.text(): self.n_title.setText(Path(path).stem)

    # ── 분석 시작 ──────────────────────────────────────────────────────────────
    def _start_analysis(self):
        api_key  = self.config.get("api_key","")
        base_url = self.config.get("base_url","")
        model    = self.model_combo.currentText()
        if not api_key:
            QMessageBox.warning(self,"API 키 없음","설정에서 API 키를 입력하세요.")
            self._open_settings(); return
        tab_idx = self.input_tabs.currentIndex()
        input_type, file_path, raw_text, metadata, topic_override = self._collect_input(tab_idx)
        if not raw_text and not file_path:
            QMessageBox.warning(self,"입력 없음","텍스트를 입력하거나 파일을 선택하세요."); return
        self.analyze_btn.setEnabled(False); self.analyze_btn.setText("⏳ 분석 중...")
        self.progress.setVisible(True); self.result_editor.clear()
        self.save_btn.setEnabled(False); self.open_btn.setEnabled(False); self._result = ""
        self._worker = AnalysisWorker(
            api_key=api_key, base_url=base_url, model=model,
            input_type=input_type, file_path=file_path, raw_text=raw_text,
            metadata=metadata, vault_path=self.config.get("vault_path",""),
            auto_save=self.auto_save_chk.isChecked(), topic_override=topic_override,
        )
        self._worker.token_received.connect(self._on_token)
        self._worker.analysis_done.connect(self._on_done)
        self._worker.save_done.connect(self._on_saved)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.status_update.connect(self._on_status)
        self._worker.engine_update.connect(self._on_engine_update)
        self._worker.start()

    def _collect_input(self, tab_idx):
        if tab_idx == 0:
            tv = self.p_topic.currentText()
            return ("paper", self._paper_file, self.p_text.toPlainText(),
                {"title":self.p_title.text(),"authors":self.p_authors.text(),
                 "year":self.p_year.text(),"journal":self.p_journal.text(),"zotero":self.p_zotero.text()},
                "" if tv == "(자동 감지)" else tv)
        elif tab_idx == 1:
            return (self.t_type.currentText(), self._transcript_file, self.t_text.toPlainText(),
                {"title":self.t_title.text(),"year":self.t_date.text(),"context":self.t_ctx.text()}, "")
        elif tab_idx == 2:
            return ("dataset", self._dataset_file, self.d_text.toPlainText(),
                {"title":self.d_name.text(),"context":self.d_ctx.text()}, "")
        elif tab_idx == 3:
            return ("equation","",self.eq_text.toPlainText(),{"context":self.eq_ctx.text()},"")
        else:
            return ("notes",self._notes_file,self.n_text.toPlainText(),
                {"title":self.n_title.text(),"context":self.n_ctx.text()},"")

    # ── 시그널 핸들러 ──────────────────────────────────────────────────────────
    @pyqtSlot(str)
    def _on_token(self, token):
        self._result += token
        cursor = self.result_editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.result_editor.setTextCursor(cursor)
        self.result_editor.ensureCursorVisible()
        self.token_count.setText(f"~{len(self._result.split())} words")

    @pyqtSlot(str)
    def _on_done(self, result):
        self._result = result
        self.analyze_btn.setEnabled(True); self.analyze_btn.setText("🚀  분석 시작  (ROS)")
        self.progress.setVisible(False); self.save_btn.setEnabled(True)
        self._refresh_vault(); self._refresh_recent(); self._update_graph_stats()
        # v6.0 인지 보조 패널 업데이트
        tab_idx = self.input_tabs.currentIndex()
        title = [self.p_title.text(), self.t_title.text(), self.d_name.text(),
                 "Equation", self.n_title.text()][tab_idx] or "Analysis"
        self._update_cog_panels(result, title)

    @pyqtSlot(str,str)
    def _on_saved(self, path, topic):
        self._saved_path = path; self._saved_topic = topic
        self.open_btn.setEnabled(True); self.topic_badge.setText(f"📁 {topic}")
        self._set_status(f"✅ 저장 완료: {Path(path).name}"); self._refresh_vault()

    @pyqtSlot(str)
    def _on_error(self, msg):
        self.analyze_btn.setEnabled(True); self.analyze_btn.setText("🚀  분석 시작  (ROS)")
        self.progress.setVisible(False); QMessageBox.critical(self,"오류",msg[:600])
        self._set_status(f"❌ 오류: {msg[:80]}")

    @pyqtSlot(str)
    def _on_status(self, msg): self._set_status(msg)

    def _toggle_dashboard(self):
        self._dash_visible = not self._dash_visible
        self._infra_dashboard.setVisible(self._dash_visible)
        arrow = "▲" if self._dash_visible else "▼"
        self._dash_toggle_btn.setText(f"⚡ v4.0 Infrastructure Monitor  {arrow}")

    @pyqtSlot(str, dict)
    def _on_engine_update(self, engine_name: str, data: dict):
        """5개 인지 엔진 + v4.0 인프라 엔진 결과 실시간 표시."""
        # InfraDashboard에 v4.0 엔진 상태 전달
        self._infra_dashboard.update_engine_status(engine_name, data)

        icons = {
            "evolution":       "🌱",
            "contradiction":   "⚡",
            "lineage":         "🧬",
            "math_ontology":   "📐",
            "tension":         "🔭",
            "security":        "🔒",
            "graph_integrity": "🕸️",
            "graph":           "🕸️",
        }
        icon = icons.get(engine_name, "🔧")
        if engine_name == "evolution":
            msg = f"{icon} Stage: {data.get('stage','?')} | Score: {data.get('score',0):.2f}"
        elif engine_name == "contradiction":
            msg = f"{icon} Contradictions: {data.get('count',0)}"
        elif engine_name == "lineage":
            msg = f"{icon} Lineage ID: {str(data.get('lineage_id',''))[:8]}..."
        elif engine_name == "math_ontology":
            msg = f"{icon} Math objects: {data.get('count',0)}"
        elif engine_name == "tension":
            msg = f"{icon} Graph: {data.get('graph_nodes',0)}N / {data.get('graph_edges',0)}E"
        elif engine_name == "security":
            msg = f"{icon} Trust: {data.get('trust_score',1.0):.2f}"
        elif engine_name in ("graph_integrity", "graph"):
            msg = f"{icon} {data.get('nodes',0)}N / {data.get('edges',0)}E"
        else:
            msg = f"{icon} {engine_name}: {data}"
        current = self.graph_stats.text()
        lines = [l for l in current.split("\n") if not l.startswith(icon)]
        lines.append(msg)
        self.graph_stats.setText("\n".join(lines[-10:]))

    # ── 저장 / 열기 ────────────────────────────────────────────────────────────
    def _manual_save(self):
        vault = self.config.get("vault_path","")
        if not vault:
            QMessageBox.warning(self,"볼트 미설정","설정에서 Obsidian 볼트 경로를 지정하세요."); return
        content = self.result_editor.toPlainText()
        if not content: return
        tab_idx = self.input_tabs.currentIndex()
        input_type = ["paper","transcript","dataset","equation","notes"][tab_idx]
        title = [self.p_title.text(),self.t_title.text(),self.d_name.text(),"Equation",self.n_title.text()][tab_idx] or "Untitled"
        journal = self.p_journal.text() if tab_idx == 0 else ""
        tv = self.p_topic.currentText() if tab_idx == 0 else ""
        topic_override = "" if tv in ("","(자동 감지)") else tv
        try:
            ok, path, topic = obsidian_sync.save_note_to_vault(
                vault_path=vault, markdown_content=content, title=title,
                input_type=input_type, journal=journal, topic_override=topic_override)
            if ok:
                self._saved_path = path; self._saved_topic = topic
                self.open_btn.setEnabled(True); self.topic_badge.setText(f"📁 {topic}")
                self._set_status(f"✅ 저장: {Path(path).name}"); self._refresh_vault()
            else: QMessageBox.critical(self,"저장 실패",path)
        except Exception as e: QMessageBox.critical(self,"저장 오류",str(e))

    def _open_obsidian(self):
        vault = self.config.get("vault_path","")
        if self._saved_path and vault: obsidian_sync.open_in_obsidian(vault, self._saved_path)

    def _copy_result(self):
        text = self.result_editor.toPlainText()
        if text: QApplication.clipboard().setText(text); self._set_status("📋 클립보드에 복사됨")

    def _clear_result(self):
        self.result_editor.clear(); self._result = ""
        self.save_btn.setEnabled(False); self.open_btn.setEnabled(False)
        self.topic_badge.setText(""); self.token_count.setText("0 words")

    # ── 볼트 탐색기 ────────────────────────────────────────────────────────────
    def _refresh_vault(self):
        vault = self.config.get("vault_path","")
        if not vault: return
        self.vault_label.setText(f"📁 {vault}")
        notes = obsidian_sync.list_notes(vault)
        stats = obsidian_sync.get_vault_stats(vault)
        self.stats_label.setText(f"총 {stats.get('total_notes',0)}개 · {len(stats.get('by_folder',{}))}개 폴더")
        self.vault_tree.clear()
        folders = {}
        for n in notes: folders.setdefault(n["folder"],[]).append(n)
        for folder, items in sorted(folders.items()):
            icon = obsidian_sync.TOPIC_ICONS.get(folder,"📄")
            parent = QTreeWidgetItem(self.vault_tree,[f"{icon} {folder} ({len(items)})",""])
            parent.setFont(0,QFont("Segoe UI",10,QFont.Weight.Bold))
            for item in items[:50]:
                child = QTreeWidgetItem(parent,[item["title"],item["modified"]])
                child.setData(0,Qt.ItemDataRole.UserRole,item["path"])
                child.setFont(0,QFont("Segoe UI",9)); child.setForeground(0,QColor("#a6adc8"))
        self.vault_tree.expandAll()

    def _open_note_from_tree(self, item, col):
        path = item.data(0,Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            vault = self.config.get("vault_path","")
            if vault: obsidian_sync.open_in_obsidian(vault,path)

    def _rebuild_index(self):
        vault = self.config.get("vault_path","")
        if not vault: return
        obsidian_sync._create_index(Path(vault))
        self._set_status("📑 인덱스 재생성 완료")

    def _scan_concepts(self):
        vault = self.config.get("vault_path","")
        if not vault: return
        concepts = obsidian_sync.scan_vault_concepts(vault)
        memory.register_concepts(concepts)
        self._set_status(f"🔍 {len(concepts)}개 개념 스캔 완료")

    def _update_graph_stats(self):
        stats = memory.get_graph_stats()
        self.graph_stats.setText(
            f"🕸 Graph: {stats.get('total_nodes',0)} nodes · {stats.get('total_edges',0)} edges\n"
            f"📄 {stats.get('note_nodes',0)} notes · 💡 {stats.get('concept_nodes',0)} concepts"
        )

    def _refresh_recent(self):
        self.recent_list.clear()
        for s in memory.load_recent_sessions(10):
            item = QTreeWidgetItem(self.recent_list,[f"{s.get('type','?')} · {s.get('title','')[:30]}"])
            item.setForeground(0,QColor("#a6adc8")); item.setFont(0,QFont("Segoe UI",9))

    # ── 설정 / 프로필 ──────────────────────────────────────────────────────────
    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec(): self._load_state()

    def _open_profile(self):
        from ui.profile_dialog import ProfileDialog
        ProfileDialog(self).exec()

    def _show_graph_stats(self):
        stats = memory.get_graph_stats()
        concepts = memory.load_concepts()
        top = sorted(concepts.items(), key=lambda x: x[1].get("count",0), reverse=True)[:10]
        top_str = "\n".join(f"  {i+1}. {k} ({v.get('count',0)}회)" for i,(k,v) in enumerate(top))
        QMessageBox.information(self,"지식 그래프 통계",
            f"총 노드: {stats['total_nodes']}\n노트: {stats['note_nodes']}\n"
            f"개념: {stats['concept_nodes']}\n엣지: {stats['total_edges']}\n\n🔝 상위 개념:\n{top_str}")

    def _show_help(self):
        QMessageBox.information(self,"사용 방법",
            "📄 Paper: 논문 PDF/텍스트 → Karpathy 스타일 위키\n"
            "🎙 Script: 강의/음성 스크립트 → 원자적 인사이트\n"
            "🗃 Dataset: CSV/Excel → 인과 설계 기회 분석\n"
            "∑ Equation: 수식 → 수학적 지식 원자\n"
            "📋 Notes: 연구 메모 → 구조화된 위키\n\n"
            "모든 노트는 [[WikiLink]]로 자동 연결됩니다.")

    def _show_about(self):
        QMessageBox.about(self,"About ROS",
            "🧠 Research Operating System v3.0\n\n"
            "경제학 연구자를 위한 AI 지식 컴파일러\n"
            "Karpathy-style atomic knowledge primitives\n\n"
            "입력: Paper · Script · Dataset · Equation · Notes\n"
            "출력: Obsidian knowledge graph")

    def _set_status(self, msg): self.status_label.setText(msg)

    def closeEvent(self, event):
        self.config.set("auto_save", self.auto_save_chk.isChecked())
        self.config.set("model", self.model_combo.currentText())
        self.config.save(); event.accept()
