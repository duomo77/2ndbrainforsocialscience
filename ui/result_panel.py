"""
result_panel.py - 분석 결과 뷰어 패널
생성된 Markdown 위키 노트 표시, 편집, Obsidian 볼트 저장
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit,
    QTabWidget, QFileDialog, QMessageBox,
    QGroupBox, QLineEdit, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter
import re


class MarkdownHighlighter(QSyntaxHighlighter):
    """간단한 Markdown 구문 강조."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # YAML Frontmatter
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#6b7280"))
        self.rules.append((re.compile(r"^---.*?---", re.DOTALL | re.MULTILINE), fmt))

        # 헤딩
        fmt_h = QTextCharFormat()
        fmt_h.setForeground(QColor("#7c3aed"))
        fmt_h.setFontWeight(700)
        self.rules.append((re.compile(r"^#{1,6}\s+.+", re.MULTILINE), fmt_h))

        # WikiLink [[...]]
        fmt_wl = QTextCharFormat()
        fmt_wl.setForeground(QColor("#0891b2"))
        fmt_wl.setFontUnderline(True)
        self.rules.append((re.compile(r"\[\[.+?\]\]"), fmt_wl))

        # LaTeX 인라인 $...$
        fmt_latex = QTextCharFormat()
        fmt_latex.setForeground(QColor("#b45309"))
        self.rules.append((re.compile(r"\$[^$\n]+\$"), fmt_latex))

        # 볼드 **...**
        fmt_bold = QTextCharFormat()
        fmt_bold.setFontWeight(700)
        self.rules.append((re.compile(r"\*\*.+?\*\*"), fmt_bold))

        # 코드 블록
        fmt_code = QTextCharFormat()
        fmt_code.setForeground(QColor("#059669"))
        fmt_code.setFontFamily("Courier New")
        self.rules.append((re.compile(r"`[^`]+`"), fmt_code))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class ResultPanel(QWidget):
    """분석 결과 패널 위젯."""

    save_to_vault_requested = pyqtSignal(str, str)  # (markdown, filename)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_markdown = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── 헤더 ──────────────────────────────────────
        header_row = QHBoxLayout()
        title_lbl = QLabel("📊 분석 결과")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title_lbl.setFont(font)
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
        header_row.addWidget(self.status_lbl)
        layout.addLayout(header_row)

        # ── 탭: 편집기 / 미리보기 ──────────────────────
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabBar::tab { padding: 6px 14px; }
            QTabBar::tab:selected { background: #7c3aed; color: white; border-radius: 4px 4px 0 0; }
        """)

        # Markdown 편집기 탭
        editor_tab = QWidget()
        editor_layout = QVBoxLayout(editor_tab)
        editor_layout.setContentsMargins(4, 4, 4, 4)

        self.markdown_editor = QTextEdit()
        self.markdown_editor.setFont(QFont("Courier New", 11))
        self.markdown_editor.setPlaceholderText(
            "분석 결과가 여기에 스트리밍됩니다...\n\n"
            "왼쪽 패널에서 논문 정보를 입력하고 '분석 시작' 버튼을 클릭하세요."
        )
        self.markdown_editor.textChanged.connect(self._on_text_changed)
        self._highlighter = MarkdownHighlighter(self.markdown_editor.document())
        editor_layout.addWidget(self.markdown_editor)
        self.tab_widget.addTab(editor_tab, "✏️ Markdown 편집기")

        layout.addWidget(self.tab_widget)

        # ── Obsidian 저장 패널 ─────────────────────────
        save_group = QGroupBox("💾 Obsidian 볼트에 저장")
        save_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #374151;
                font-size: 11px;
            }
        """)
        save_layout = QVBoxLayout(save_group)

        # 파일명 입력
        fn_row = QHBoxLayout()
        fn_row.addWidget(QLabel("파일명:"))
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("비워두면 frontmatter에서 자동 생성")
        fn_row.addWidget(self.filename_edit)
        save_layout.addLayout(fn_row)

        # 저장 버튼 행
        btn_row = QHBoxLayout()

        self.copy_btn = QPushButton("📋 클립보드 복사")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        self.copy_btn.setStyleSheet(
            "QPushButton { border: 1px solid #d1d5db; border-radius: 4px; padding: 6px 12px; }"
            "QPushButton:hover { background: #f3f4f6; }"
        )

        self.export_btn = QPushButton("📁 파일로 내보내기")
        self.export_btn.clicked.connect(self._export_to_file)
        self.export_btn.setStyleSheet(self.copy_btn.styleSheet())

        self.vault_btn = QPushButton("🏛 Obsidian 볼트에 저장")
        self.vault_btn.setStyleSheet(
            "QPushButton { background: #7c3aed; color: white; border-radius: 4px; "
            "padding: 6px 16px; font-weight: bold; }"
            "QPushButton:hover { background: #6d28d9; }"
            "QPushButton:disabled { background: #c4b5fd; }"
        )
        self.vault_btn.clicked.connect(self._save_to_vault)

        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.vault_btn)
        save_layout.addLayout(btn_row)

        # 저장 결과 표시
        self.save_result_lbl = QLabel("")
        self.save_result_lbl.setWordWrap(True)
        self.save_result_lbl.setStyleSheet("font-size: 11px;")
        save_layout.addWidget(self.save_result_lbl)

        layout.addWidget(save_group)

    def _on_text_changed(self):
        self._current_markdown = self.markdown_editor.toPlainText()

    def append_token(self, token: str):
        """스트리밍 토큰 추가."""
        cursor = self.markdown_editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.markdown_editor.setTextCursor(cursor)
        self.markdown_editor.ensureCursorVisible()

    def set_result(self, markdown: str):
        """분석 완료 후 전체 결과 설정."""
        self._current_markdown = markdown
        self.markdown_editor.setPlainText(markdown)
        self.status_lbl.setText(f"✅ 완료 ({len(markdown):,}자)")
        self.status_lbl.setStyleSheet("color: #059669; font-size: 11px;")

    def set_streaming(self, is_streaming: bool):
        """스트리밍 상태 표시."""
        if is_streaming:
            self.markdown_editor.clear()
            self.status_lbl.setText("⏳ 분석 중...")
            self.status_lbl.setStyleSheet("color: #7c3aed; font-size: 11px;")
        self.vault_btn.setEnabled(not is_streaming)

    def set_auto_save_result(self, success: bool, path: str):
        """자동 저장 결과 표시."""
        if success:
            self.save_result_lbl.setText(f"✅ 자동 저장 완료: {path}")
            self.save_result_lbl.setStyleSheet("color: #059669; font-size: 11px;")
        else:
            self.save_result_lbl.setText(f"⚠️ 자동 저장 실패: {path}")
            self.save_result_lbl.setStyleSheet("color: #dc2626; font-size: 11px;")

    def _copy_to_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._current_markdown)
        self.save_result_lbl.setText("📋 클립보드에 복사되었습니다.")
        self.save_result_lbl.setStyleSheet("color: #059669; font-size: 11px;")

    def _export_to_file(self):
        if not self._current_markdown:
            QMessageBox.warning(self, "경고", "저장할 내용이 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Markdown 파일 저장", "wiki_note.md", "Markdown (*.md)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._current_markdown)
            self.save_result_lbl.setText(f"✅ 저장됨: {path}")
            self.save_result_lbl.setStyleSheet("color: #059669; font-size: 11px;")

    def _save_to_vault(self):
        if not self._current_markdown:
            QMessageBox.warning(self, "경고", "저장할 내용이 없습니다.")
            return
        filename = self.filename_edit.text().strip()
        self.save_to_vault_requested.emit(self._current_markdown, filename)
