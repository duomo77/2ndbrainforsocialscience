"""
settings_dialog.py - API 키 및 앱 설정 다이얼로그
탭 구성:
  1. API 설정 (키, 모델, Base URL)
  2. Obsidian 볼트 설정
  3. 분류 규칙 편집 (저널 → 주제 폴더 매핑)
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QGroupBox, QMessageBox, QFileDialog,
    QTextEdit, QFrame, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QColor

from core.config import load_config, save_config
from core.worker import ValidationWorker


# ── 글로벌 Provider ────────────────────────────────────────────────────────
PRESET_MODELS_GLOBAL = [
    # OpenAI current generation
    "gpt-5.2",
    "gpt-5.2-pro",
    "gpt-5.1",
    "gpt-5.1-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    # Still useful fallbacks
    "gpt-4.1",
    "gpt-4.1-mini",
    "o3",
    "o4-mini",
    # OpenAI-compatible third-party endpoints
    "gemini-3.1-pro",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "claude-opus-4-6",
    "claude-sonnet-4-5",
    "llama-4-maverick-17b-128e-instruct",
    "llama-4-scout-17b-16e-instruct",
]

# ── 중국 Provider 모델 목록 ─────────────────────────────────────────────────
PRESET_MODELS_CHINA = {
    # DeepSeek — https://platform.deepseek.com
    "DeepSeek (深度求索)": [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    ],
    # Qwen / 通义千问 — https://dashscope.aliyuncs.com
    "Qwen / 通义千问 (Alibaba)": [
        "qwen3-max",
        "qwen3-max-thinking",
        "qwen3.5-plus",
        "qwen3.5-flash",
        "qwen3-coder-plus",
        "qwen3-coder-flash",
        "qwen-max",
        "qwen-plus",
        "qwen-long",
        "qwen3-235b-a22b",
        "qwen3-72b",
    ],
    # Zhipu GLM / 智谱 — https://open.bigmodel.cn
    "Zhipu GLM (智谱AI)": [
        "glm-5.1",
        "glm-5-air",
        "glm-4.6",
        "glm-4.5",
        "glm-4-plus",
        "glm-4-flash",
        "glm-4-long",
        "glm-z1-plus",
        "glm-z1-air",
    ],
    # Moonshot Kimi — https://platform.moonshot.ai
    "Moonshot Kimi (月之暗面)": [
        "kimi-k2.5",
        "kimi-k2-thinking",
        "kimi-k2-turbo-preview",
        "kimi-k2.6",
        "kimi-k2",
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
    ],
    # MiniMax — https://api.minimax.chat
    "MiniMax (稀宇科技)": [
        "MiniMax-M2.7",
        "MiniMax-M2",
        "MiniMax-M1",
        "MiniMax-Text-01",
    ],
    # Baidu ERNIE / 文心一言 — https://aistudio.baidu.com
    "Baidu ERNIE (文心一言)": [
        "ernie-5.0",
        "ernie-5.0-turbo",
        "ernie-4.5-turbo-128k",
        "ernie-4.5-8k",
        "ernie-x1-turbo-32k",
        "ernie-x1-32k",
    ],
    # SiliconFlow — https://api.siliconflow.cn (중국 멀티모델 게이트웨이)
    "SiliconFlow (硅基流动)": [
        "deepseek-ai/DeepSeek-V4-Pro",
        "deepseek-ai/DeepSeek-V4-Flash",
        "moonshotai/Kimi-K2.6",
        "Qwen/Qwen3.6-35B-A3B",
        "Qwen/Qwen3.6-27B",
        "Qwen/Qwen3.5-397B-A17B",
        "Qwen/Qwen3.5-122B-A10B",
        "Qwen/Qwen3-235B-A22B",
        "Qwen/Qwen3-72B",
        "zai-org/GLM-5.1",
        "THUDM/GLM-4.6V",
        "MiniMaxAI/MiniMax-M2",
        "openai/gpt-oss-120b",
    ],
    # 01.AI / 零一万物 — https://api.lingyiwanwu.com
    "01.AI / 零一万物": [
        "yi-lightning",
        "yi-lightning-lite",
        "yi-large",
        "yi-large-turbo",
        "yi-large-rag",
    ],
}

# ── Base URL 매핑 ────────────────────────────────────────────────────────────
PRESET_BASE_URLS = {
    # ── 글로벌 ─────────────────────────────────────────
    "OpenAI (기본)":                  "https://api.openai.com/v1",
    "Azure OpenAI":                   "https://YOUR_RESOURCE.openai.azure.com/",
    "Anthropic (호환)":               "https://api.anthropic.com/v1",
    "Groq":                           "https://api.groq.com/openai/v1",
    # ── 중국 ───────────────────────────────────────────
    "DeepSeek (深度求索)":             "https://api.deepseek.com",
    "Qwen / 通义千问 (Alibaba)":       "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "Zhipu GLM (智谱AI)":             "https://open.bigmodel.cn/api/paas/v4",
    "Moonshot Kimi (月之暗面)":        "https://api.moonshot.ai/v1",
    "MiniMax (稀宇科技)":              "https://api.minimax.chat/v1",
    "Baidu ERNIE (文心一言)":          "https://qianfan.baidubce.com/v2",
    "SiliconFlow (硅基流动)":          "https://api.siliconflow.cn/v1",
    "01.AI / 零一万物":                "https://api.lingyiwanwu.com/v1",
    # ── 기타 ───────────────────────────────────────────
    "직접 입력":                       "",
}

# Provider → 카테고리 분류 (UI 구분선용)
PROVIDER_CATEGORIES = {
    "글로벌": ["OpenAI (기본)", "Azure OpenAI", "Anthropic (호환)", "Groq"],
    "중국 (China)": [
        "DeepSeek (深度求索)",
        "Qwen / 通义千问 (Alibaba)",
        "Zhipu GLM (智谱AI)",
        "Moonshot Kimi (月之暗面)",
        "MiniMax (稀宇科技)",
        "Baidu ERNIE (文心一言)",
        "SiliconFlow (硅基流动)",
        "01.AI / 零一万物",
    ],
    "기타": ["직접 입력"],
}

# 모든 모델 목록 (글로벌 + 중국)
PRESET_MODELS = PRESET_MODELS_GLOBAL + [
    m for models in PRESET_MODELS_CHINA.values() for m in models
]


class SettingsDialog(QDialog):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        # Config 객체 또는 None 모두 지원
        if config is not None and hasattr(config, "_data"):
            self.config = config._data
            self._config_obj = config
        else:
            self.config = load_config()
            self._config_obj = None
        self._validation_worker = None
        self.setWindowTitle("⚙️ 설정 — Research Operating System")
        self.setMinimumSize(680, 600)
        self.setModal(True)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── 헤더 ──────────────────────────────────────
        header = QLabel("ECONOMETRIC COMPILER V1.0 — 설정")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        header.setFont(font)
        header.setStyleSheet("color: #7c3aed; padding: 6px;")
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(sep)

        # ── 탭 위젯 ───────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { padding: 7px 18px; font-size: 12px; }
            QTabBar::tab:selected {
                background: #7c3aed; color: white;
                border-radius: 4px 4px 0 0;
            }
        """)

        self.tabs.addTab(self._build_api_tab(),        "🔑 API 설정")
        self.tabs.addTab(self._build_vault_tab(),      "📂 볼트 설정")
        self.tabs.addTab(self._build_classify_tab(),   "🗂 분류 규칙")
        self.tabs.addTab(self._build_concepts_tab(),   "🔗 위키 개념")

        layout.addWidget(self.tabs)

        # ── 저장/취소 버튼 ─────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "QPushButton { border: 1px solid #d1d5db; border-radius: 4px; padding: 6px 18px; }"
        )

        save_btn = QPushButton("💾 저장")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_settings)
        save_btn.setStyleSheet(
            "QPushButton { background: #059669; color: white; border-radius: 4px; "
            "padding: 6px 18px; font-weight: bold; }"
            "QPushButton:hover { background: #047857; }"
        )

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    # ── 탭 1: API 설정 ─────────────────────────────────
    def _build_api_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        group = QGroupBox("LLM API 연결 설정")
        group.setStyleSheet(self._group_style())
        form = QFormLayout(group)
        form.setSpacing(10)

        self.provider_combo = QComboBox()
        self._populate_provider_combo()
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        form.addRow("Base URL:", self.base_url_edit)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-... 또는 해당 서비스 API 키")
        show_btn = QPushButton("👁")
        show_btn.setFixedWidth(32)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda c: self.api_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password
            )
        )
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key_edit)
        key_row.addWidget(show_btn)
        form.addRow("API Key:", key_row)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(PRESET_MODELS_GLOBAL)
        form.addRow("Model:", self.model_combo)

        # API 키 발급 링크
        self.api_link_lbl = QLabel()
        self.api_link_lbl.setOpenExternalLinks(True)
        self.api_link_lbl.setStyleSheet("font-size: 10px; color: #6b7280;")
        self._update_api_link("OpenAI (기본)")
        form.addRow("", self.api_link_lbl)

        self.validate_btn = QPushButton("🔗 API 연결 테스트")
        self.validate_btn.setStyleSheet(
            "QPushButton { background: #7c3aed; color: white; border-radius: 4px; padding: 5px 12px; }"
            "QPushButton:hover { background: #6d28d9; }"
        )
        self.validate_btn.clicked.connect(self._validate_api)
        self.validate_status = QLabel("")
        self.validate_status.setWordWrap(True)
        val_row = QHBoxLayout()
        val_row.addWidget(self.validate_btn)
        val_row.addWidget(self.validate_status, 1)
        form.addRow("", val_row)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    # ── 탭 2: 볼트 설정 ────────────────────────────────
    def _build_vault_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        group = QGroupBox("Obsidian 볼트 경로 및 저장 옵션")
        group.setStyleSheet(self._group_style())
        form = QFormLayout(group)
        form.setSpacing(10)

        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setPlaceholderText("/path/to/ObsidianVault")
        browse_btn = QPushButton("📁 찾아보기")
        browse_btn.clicked.connect(self._browse_vault)
        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_path_edit)
        vault_row.addWidget(browse_btn)
        form.addRow("볼트 경로:", vault_row)

        self.subfolder_edit = QLineEdit()
        self.subfolder_edit.setPlaceholderText("Papers")
        form.addRow("기본 저장 폴더:", self.subfolder_edit)

        self.auto_sync_check = QCheckBox("분석 완료 시 자동으로 볼트에 저장")
        self.auto_sync_check.setChecked(True)
        form.addRow("", self.auto_sync_check)

        self.auto_index_check = QCheckBox("_INDEX.md (MOC) 자동 업데이트")
        self.auto_index_check.setChecked(True)
        form.addRow("", self.auto_index_check)

        # 주제 폴더 사용 옵션
        self.use_topic_folders_check = QCheckBox(
            "주제별 서브폴더에 저장 (예: Papers/Econometrics/, Papers/MachineLearning/)"
        )
        self.use_topic_folders_check.setChecked(True)
        self.use_topic_folders_check.setStyleSheet("font-weight: bold; color: #5b21b6;")
        form.addRow("", self.use_topic_folders_check)

        self.llm_classify_check = QCheckBox(
            "규칙 매핑 실패 시 LLM으로 주제 분류 (API 호출 추가 발생)"
        )
        self.llm_classify_check.setChecked(True)
        form.addRow("", self.llm_classify_check)

        layout.addWidget(group)

        # 폴더 구조 미리보기
        preview_group = QGroupBox("볼트 폴더 구조 미리보기")
        preview_group.setStyleSheet(self._group_style())
        preview_layout = QVBoxLayout(preview_group)
        self.folder_preview = QLabel()
        self.folder_preview.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 11px; "
            "color: #374151; padding: 8px; background: #f9fafb; border-radius: 4px;"
        )
        self.folder_preview.setWordWrap(True)
        self._update_folder_preview()
        self.vault_path_edit.textChanged.connect(self._update_folder_preview)
        self.subfolder_edit.textChanged.connect(self._update_folder_preview)
        self.use_topic_folders_check.toggled.connect(self._update_folder_preview)
        preview_layout.addWidget(self.folder_preview)
        layout.addWidget(preview_group)

        layout.addStretch()
        return tab

    def _update_folder_preview(self):
        vault = self.vault_path_edit.text().strip() or "/YourVault"
        sub = self.subfolder_edit.text().strip() or "Papers"
        use_topics = self.use_topic_folders_check.isChecked()

        if use_topics:
            preview = (
                f"{vault}/\n"
                f"└── {sub}/\n"
                f"    ├── 📐 Econometrics/\n"
                f"    │   ├── Chernozhukov (2018) - DML.md\n"
                f"    │   └── Athey (2019) - Causal Forest.md\n"
                f"    ├── 🤖 MachineLearning/\n"
                f"    │   └── Breiman (2001) - Random Forests.md\n"
                f"    ├── 📊 GeneralEconomics/\n"
                f"    ├── 📝 WorkingPapers/\n"
                f"    ├── 📂 Uncategorized/\n"
                f"    └── _INDEX.md  ← MOC (자동 생성)"
            )
        else:
            preview = (
                f"{vault}/\n"
                f"└── {sub}/\n"
                f"    ├── Chernozhukov (2018) - DML.md\n"
                f"    ├── Athey (2019) - Causal Forest.md\n"
                f"    └── _INDEX.md  ← MOC (자동 생성)"
            )
        self.folder_preview.setText(preview)

    # ── 탭 3: 분류 규칙 편집 ───────────────────────────
    def _build_classify_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "저널명 패턴(부분 일치, 소문자)과 저장 폴더명을 매핑합니다.\n"
            "사용자 규칙이 내장 규칙보다 우선 적용됩니다. "
            "폴더명은 영문 권장 (예: Econometrics, MyJournals)."
        )
        hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 규칙 테이블
        self.rules_table = QTableWidget(0, 2)
        self.rules_table.setHorizontalHeaderLabels(["저널명 패턴 (부분 일치)", "주제 폴더명"])
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.rules_table.setColumnWidth(1, 200)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setStyleSheet("""
            QTableWidget { border: 1px solid #e5e7eb; border-radius: 4px; font-size: 11px; }
            QTableWidget::item { padding: 4px 8px; }
            QHeaderView::section {
                background: #f3f4f6; padding: 5px 8px;
                border: none; border-bottom: 1px solid #e5e7eb;
                font-weight: bold; font-size: 11px;
            }
        """)
        layout.addWidget(self.rules_table)

        # 테이블 버튼 행
        tbl_btn_row = QHBoxLayout()

        add_btn = QPushButton("➕ 규칙 추가")
        add_btn.clicked.connect(self._add_rule_row)
        add_btn.setStyleSheet(
            "QPushButton { background: #059669; color: white; border-radius: 4px; padding: 5px 12px; }"
            "QPushButton:hover { background: #047857; }"
        )

        del_btn = QPushButton("➖ 선택 삭제")
        del_btn.clicked.connect(self._delete_rule_row)
        del_btn.setStyleSheet(
            "QPushButton { background: #dc2626; color: white; border-radius: 4px; padding: 5px 12px; }"
            "QPushButton:hover { background: #b91c1c; }"
        )

        tbl_btn_row.addWidget(add_btn)
        tbl_btn_row.addWidget(del_btn)
        tbl_btn_row.addStretch()
        layout.addLayout(tbl_btn_row)

        # 내장 규칙 미리보기
        builtin_group = QGroupBox("내장 저널 매핑 (참고용 — 수정 불가)")
        builtin_group.setStyleSheet(self._group_style())
        builtin_layout = QVBoxLayout(builtin_group)
        builtin_layout.setContentsMargins(6, 10, 6, 6)

        builtin_text = QTextEdit()
        builtin_text.setReadOnly(True)
        builtin_text.setMaximumHeight(130)
        builtin_text.setStyleSheet(
            "font-family: 'Courier New'; font-size: 10px; "
            "background: #f9fafb; border: none;"
        )
        from core.classifier import BUILTIN_JOURNAL_MAP
        builtin_text.setPlainText(
            "\n".join(f"{k:45s} → {v}" for k, v in BUILTIN_JOURNAL_MAP.items())
        )
        builtin_layout.addWidget(builtin_text)
        layout.addWidget(builtin_group)

        return tab

    def _add_rule_row(self):
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        self.rules_table.setItem(row, 0, QTableWidgetItem("저널명 패턴"))
        self.rules_table.setItem(row, 1, QTableWidgetItem("FolderName"))

    def _delete_rule_row(self):
        rows = sorted(
            set(i.row() for i in self.rules_table.selectedItems()),
            reverse=True
        )
        for r in rows:
            self.rules_table.removeRow(r)

    # ── 탭 4: 위키 개념 ────────────────────────────────
    def _build_concepts_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "한 줄에 하나씩 입력 (예: DML, Causal Forest, IV)\n"
            "볼트 경로 설정 후 '볼트에서 자동 스캔' 버튼으로 자동 수집 가능"
        )
        hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.concepts_edit = QTextEdit()
        self.concepts_edit.setPlaceholderText(
            "DML\nCausal Forest\nIV\nDID\nRDD\nConditional Independence Assumption\n..."
        )
        layout.addWidget(self.concepts_edit)

        scan_btn = QPushButton("🔍 볼트에서 자동 스캔")
        scan_btn.clicked.connect(self._scan_vault_concepts)
        scan_btn.setStyleSheet(
            "QPushButton { border: 1px solid #7c3aed; color: #7c3aed; "
            "border-radius: 4px; padding: 5px 12px; }"
            "QPushButton:hover { background: #f5f3ff; }"
        )
        layout.addWidget(scan_btn)
        return tab

    # ── 값 로드 ────────────────────────────────────────
    def _load_values(self):
        self.api_key_edit.setText(self.config.get("api_key", ""))
        self.base_url_edit.setText(
            self.config.get("api_base_url", "https://api.openai.com/v1")
        )
        model = self.config.get("model", "gpt-4o")
        idx = self.model_combo.findText(model)
        self.model_combo.setCurrentIndex(idx if idx >= 0 else 0)
        if idx < 0:
            self.model_combo.setCurrentText(model)

        self.vault_path_edit.setText(self.config.get("obsidian_vault_path", ""))
        self.subfolder_edit.setText(self.config.get("obsidian_subfolder", "Papers"))
        self.auto_sync_check.setChecked(self.config.get("auto_sync", True))
        self.auto_index_check.setChecked(self.config.get("auto_index", True))
        self.use_topic_folders_check.setChecked(self.config.get("use_topic_folders", True))
        self.llm_classify_check.setChecked(self.config.get("llm_classify_fallback", True))

        # 분류 규칙 테이블 로드
        rules = self.config.get("classification_rules", {})
        for pattern, folder in rules.items():
            row = self.rules_table.rowCount()
            self.rules_table.insertRow(row)
            self.rules_table.setItem(row, 0, QTableWidgetItem(pattern))
            self.rules_table.setItem(row, 1, QTableWidgetItem(folder))

        # 개념 목록
        concepts = self.config.get("existing_concepts", [])
        self.concepts_edit.setPlainText("\n".join(concepts))

    # ── Provider 콤보박스 구성 ─────────────────────────────────────────────
    def _populate_provider_combo(self):
        """Provider 콤보박스에 카테고리 구분선 포함하여 항목 추가."""
        from PyQt6.QtGui import QStandardItem, QStandardItemModel
        model = QStandardItemModel()

        for category, providers in PROVIDER_CATEGORIES.items():
            sep = QStandardItem(f"── {category} ──")
            sep.setEnabled(False)
            sep_font = QFont()
            sep_font.setBold(True)
            sep_font.setPointSize(9)
            sep.setFont(sep_font)
            sep.setForeground(QColor("#9ca3af"))
            model.appendRow(sep)

            for provider in providers:
                item = QStandardItem(f"  {provider}")
                item.setData(provider, Qt.ItemDataRole.UserRole)
                model.appendRow(item)

        self.provider_combo.setModel(model)
        for i in range(model.rowCount()):
            if model.item(i).isEnabled():
                self.provider_combo.setCurrentIndex(i)
                break

    def _get_current_provider(self) -> str:
        """Provider 콤보박스에서 실제 Provider 이름 반환."""
        idx = self.provider_combo.currentIndex()
        mdl = self.provider_combo.model()
        if mdl:
            item = mdl.item(idx)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                return data if data else item.text().strip()
        return self.provider_combo.currentText().strip()

    def _update_api_link(self, provider: str):
        """Provider에 맞는 API 키 발급 링크 표시."""
        links = {
            "OpenAI (기본)":                  "<a href='https://platform.openai.com/api-keys'>키 발급</a>",
            "Azure OpenAI":                   "<a href='https://portal.azure.com'>키 발급</a>",
            "Anthropic (호환)":               "<a href='https://console.anthropic.com/settings/keys'>키 발급</a>",
            "Groq":                           "<a href='https://console.groq.com/keys'>키 발급</a>",
            "DeepSeek (深度求索)":             "<a href='https://platform.deepseek.com/api_keys'>키 발급</a> | 모델: deepseek-v4-pro, deepseek-v4-flash",
            "Qwen / 通义千问 (Alibaba)":       "<a href='https://bailian.console.aliyun.com/'>키 발급 (DashScope)</a> | 모델: qwen3-max, qwen3.5-*, qwen3-coder-*",
            "Zhipu GLM (智谱AI)":             "<a href='https://open.bigmodel.cn/usercenter/apikeys'>키 발급</a> | 모델: glm-5.*, glm-4.6, glm-z1-*",
            "Moonshot Kimi (月之暗面)":        "<a href='https://platform.kimi.ai/console/api-keys'>키 발급</a> | 모델: kimi-k2.5, kimi-k2-thinking",
            "MiniMax (稀宇科技)":              "<a href='https://platform.minimaxi.com/user-center/basic-information/interface-key'>키 발급</a> | 모델: MiniMax-M2.7, MiniMax-M2",
            "Baidu ERNIE (文心一言)":          "<a href='https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application'>키 발급</a> | 모델: ernie-5.0, ernie-4.5-*, ernie-x1-*",
            "SiliconFlow (硅基流动)":          "<a href='https://cloud.siliconflow.cn/account/ak'>키 발급</a> | DeepSeek V4/Qwen3.6/GLM/Kimi 멀티모델",
            "01.AI / 零一万物":                "<a href='https://platform.lingyiwanwu.com/apikeys'>키 발급</a> | 모델: yi-lightning, yi-large",
        }
        if hasattr(self, 'api_link_lbl'):
            self.api_link_lbl.setText(links.get(provider, ""))

    def _update_model_list(self, provider: str):
        """Provider에 맞는 모델 목록으로 콤보박스 업데이트."""
        current_model = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        if provider in PRESET_MODELS_CHINA:
            models = PRESET_MODELS_CHINA[provider]
        else:
            models = PRESET_MODELS_GLOBAL

        self.model_combo.addItems(models)
        idx = self.model_combo.findText(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        elif models:
            self.model_combo.setCurrentIndex(0)
        self.model_combo.blockSignals(False)

    # ── 이벤트 핸들러 ──────────────────────────────────
    def _on_provider_changed(self, text: str):
        provider = self._get_current_provider()
        if not provider or provider.startswith("──"):
            return
        url = PRESET_BASE_URLS.get(provider, "")
        if url:
            self.base_url_edit.setText(url)
        self._update_model_list(provider)
        self._update_api_link(provider)

    def _browse_vault(self):
        path = QFileDialog.getExistingDirectory(self, "Obsidian 볼트 폴더 선택")
        if path:
            self.vault_path_edit.setText(path)

    def _validate_api(self):
        self.validate_btn.setEnabled(False)
        self.validate_status.setText("⏳ 검증 중...")
        self.validate_status.setStyleSheet("color: #6b7280;")
        self._validation_worker = ValidationWorker(
            api_key=self.api_key_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
            model=self.model_combo.currentText().strip(),
        )
        self._validation_worker.validation_complete.connect(self._on_validation_done)
        self._validation_worker.start()

    @pyqtSlot(bool, str)
    def _on_validation_done(self, success: bool, message: str):
        self.validate_btn.setEnabled(True)
        if success:
            self.validate_status.setText(f"✅ {message}")
            self.validate_status.setStyleSheet("color: #059669; font-weight: bold;")
        else:
            self.validate_status.setText(f"❌ {message}")
            self.validate_status.setStyleSheet("color: #dc2626;")

    def _scan_vault_concepts(self):
        vault_path = self.vault_path_edit.text().strip()
        subfolder = self.subfolder_edit.text().strip()
        if not vault_path:
            QMessageBox.warning(self, "경고", "볼트 경로를 먼저 설정해주세요.")
            return
        try:
            from core.obsidian_sync import scan_vault_concepts
            concepts = scan_vault_concepts(vault_path, subfolder)
            self.concepts_edit.setPlainText("\n".join(concepts))
            QMessageBox.information(self, "스캔 완료", f"{len(concepts)}개의 개념을 발견했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ── 저장 ───────────────────────────────────────────
    def _save_settings(self):
        # 분류 규칙 수집
        rules = {}
        for row in range(self.rules_table.rowCount()):
            p_item = self.rules_table.item(row, 0)
            f_item = self.rules_table.item(row, 1)
            if p_item and f_item:
                p = p_item.text().strip()
                f = f_item.text().strip()
                if p and f:
                    rules[p] = f

        concepts_text = self.concepts_edit.toPlainText().strip()
        concepts = [c.strip() for c in concepts_text.splitlines() if c.strip()]

        self.config.update({
            "api_key":              self.api_key_edit.text().strip(),
            "api_base_url":         self.base_url_edit.text().strip(),
            "model":                self.model_combo.currentText().strip(),
            "obsidian_vault_path":  self.vault_path_edit.text().strip(),
            "obsidian_subfolder":   self.subfolder_edit.text().strip(),
            "auto_sync":            self.auto_sync_check.isChecked(),
            "auto_index":           self.auto_index_check.isChecked(),
            "use_topic_folders":    self.use_topic_folders_check.isChecked(),
            "llm_classify_fallback": self.llm_classify_check.isChecked(),
            "classification_rules": rules,
            "existing_concepts":    concepts,
        })
        save_config(self.config)
        # Config 객체 동기화
        if self._config_obj is not None:
            self._config_obj._data.update(self.config)
        self.accept()

    def _group_style(self) -> str:
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """
