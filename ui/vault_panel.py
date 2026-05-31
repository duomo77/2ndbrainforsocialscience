"""
vault_panel.py - Obsidian 볼트 탐색기 패널
주제별 폴더 트리, 노트 목록, 통계 표시
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QMessageBox, QMenu, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
import os
from pathlib import Path


class VaultPanel(QWidget):
    """볼트 탐색기 패널."""

    note_open_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vault_path = ""
        self._subfolder = ""
        self._use_topic_folders = True
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        # ── 헤더 ──────────────────────────────────────
        header_row = QHBoxLayout()
        title_lbl = QLabel("🏛 볼트 탐색기")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        title_lbl.setFont(font)
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(28)
        refresh_btn.setToolTip("목록 새로고침")
        refresh_btn.setStyleSheet(
            "QPushButton { border: 1px solid #e5e7eb; border-radius: 4px; }"
            "QPushButton:hover { background: #f3f4f6; }"
        )
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # ── 볼트 정보 ──────────────────────────────────
        self.vault_info_lbl = QLabel("볼트 미설정")
        self.vault_info_lbl.setStyleSheet(
            "color: #6b7280; font-size: 10px; padding: 2px 0;"
        )
        self.vault_info_lbl.setWordWrap(True)
        layout.addWidget(self.vault_info_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(sep)

        # ── 트리 위젯 (주제 폴더 + 노트) ──────────────
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 3px 4px;
            }
            QTreeWidget::item:selected {
                background: #ede9fe;
                color: #5b21b6;
            }
            QTreeWidget::item:hover {
                background: #f5f3ff;
            }
        """)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        # ── 통계 ───────────────────────────────────────
        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet(
            "color: #6b7280; font-size: 10px; padding: 2px 0;"
        )
        layout.addWidget(self.stats_lbl)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(sep2)

        # ── 액션 버튼 ──────────────────────────────────
        btn_style = (
            "QPushButton { border: 1px solid #d1d5db; border-radius: 4px; "
            "padding: 4px 8px; font-size: 10px; }"
            "QPushButton:hover { background: #f3f4f6; }"
        )

        self.index_btn = QPushButton("📋 인덱스(MOC) 업데이트")
        self.index_btn.setStyleSheet(btn_style)
        self.index_btn.clicked.connect(self._update_index)
        layout.addWidget(self.index_btn)

        open_folder_btn = QPushButton("📂 폴더 열기")
        open_folder_btn.setStyleSheet(btn_style)
        open_folder_btn.clicked.connect(self._open_folder)
        layout.addWidget(open_folder_btn)

    # ── 볼트 설정 및 새로고침 ──────────────────────────
    def set_vault(self, vault_path: str, subfolder: str, use_topic_folders: bool = True):
        self._vault_path = vault_path
        self._subfolder = subfolder
        self._use_topic_folders = use_topic_folders
        if vault_path:
            target = Path(vault_path) / subfolder if subfolder else Path(vault_path)
            self.vault_info_lbl.setText(f"📁 {target}")
        self.refresh()

    def refresh(self):
        """트리 새로고침."""
        self.tree.clear()
        if not self._vault_path:
            self.stats_lbl.setText("")
            return

        base = (
            Path(self._vault_path) / self._subfolder
            if self._subfolder else Path(self._vault_path)
        )
        if not base.exists():
            self.stats_lbl.setText("폴더 없음")
            return

        total_notes = 0

        if self._use_topic_folders:
            # 주제 폴더 트리 구성
            from core.classifier import TOPIC_META

            # 주제 폴더들 먼저
            topic_dirs = sorted(
                [d for d in base.iterdir() if d.is_dir() and not d.name.startswith("_")],
                key=lambda x: x.name,
            )
            for topic_dir in topic_dirs:
                notes = sorted(
                    [f for f in topic_dir.glob("*.md") if not f.name.startswith("_")],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True,
                )
                if not notes:
                    continue

                meta = TOPIC_META.get(topic_dir.name, {"icon": "📂", "label": topic_dir.name})
                folder_item = QTreeWidgetItem(self.tree)
                folder_item.setText(
                    0, f"{meta['icon']} {topic_dir.name}  ({len(notes)})"
                )
                folder_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "path": str(topic_dir)})
                folder_item.setForeground(0, QBrush(QColor("#5b21b6")))
                font = QFont()
                font.setBold(True)
                folder_item.setFont(0, font)
                folder_item.setToolTip(0, meta.get("desc", ""))

                for note in notes:
                    note_item = QTreeWidgetItem(folder_item)
                    note_item.setText(0, f"  📄 {note.stem}")
                    note_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "note", "path": str(note)})
                    import datetime
                    mtime = datetime.datetime.fromtimestamp(note.stat().st_mtime)
                    note_item.setToolTip(0, f"수정: {mtime.strftime('%Y-%m-%d %H:%M')}\n{note}")
                    total_notes += 1

                folder_item.setExpanded(True)

            # 루트 노트 (분류 안 된 것)
            root_notes = sorted(
                [f for f in base.glob("*.md") if not f.name.startswith("_")],
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            if root_notes:
                root_item = QTreeWidgetItem(self.tree)
                root_item.setText(0, f"📂 (루트)  ({len(root_notes)})")
                root_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "path": str(base)})
                for note in root_notes:
                    note_item = QTreeWidgetItem(root_item)
                    note_item.setText(0, f"  📄 {note.stem}")
                    note_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "note", "path": str(note)})
                    total_notes += 1
                root_item.setExpanded(True)
        else:
            # 평면 목록
            notes = sorted(
                [f for f in base.glob("*.md") if not f.name.startswith("_")],
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            for note in notes:
                item = QTreeWidgetItem(self.tree)
                item.setText(0, f"📄 {note.stem}")
                item.setData(0, Qt.ItemDataRole.UserRole, {"type": "note", "path": str(note)})
                total_notes += 1

        self.stats_lbl.setText(f"총 {total_notes}개 노트")

    # ── 이벤트 핸들러 ──────────────────────────────────
    def _on_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("type") == "note":
            self._open_note_file(data["path"])

    def _open_note_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.note_open_requested.emit(content)
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)

        if data.get("type") == "note":
            open_action = menu.addAction("📖 편집기에서 열기")
            open_os_action = menu.addAction("🖥 파일 탐색기에서 열기")
            menu.addSeparator()
            delete_action = menu.addAction("🗑 삭제")

            action = menu.exec(self.tree.mapToGlobal(pos))
            path = data["path"]

            if action == open_action:
                self._open_note_file(path)
            elif action == open_os_action:
                self._reveal_in_os(path)
            elif action == delete_action:
                reply = QMessageBox.question(
                    self, "삭제 확인",
                    f"'{Path(path).stem}' 노트를 삭제하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    os.remove(path)
                    self.refresh()

        elif data.get("type") == "folder":
            open_os_action = menu.addAction("📂 폴더 열기")
            action = menu.exec(self.tree.mapToGlobal(pos))
            if action == open_os_action:
                self._reveal_in_os(data["path"], is_folder=True)

    def _reveal_in_os(self, path: str, is_folder: bool = False):
        import subprocess, sys
        target = path if is_folder else str(Path(path).parent)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path if not is_folder else target])
            elif sys.platform == "win32":
                if is_folder:
                    subprocess.run(["explorer", target])
                else:
                    subprocess.run(["explorer", "/select,", path])
            else:
                subprocess.run(["xdg-open", target])
        except Exception:
            pass

    def _update_index(self):
        if not self._vault_path:
            QMessageBox.warning(self, "경고", "볼트 경로가 설정되지 않았습니다.")
            return
        try:
            from core.obsidian_sync import get_vault_notes_metadata, create_index_note
            metadata = get_vault_notes_metadata(
                self._vault_path, self._subfolder, self._use_topic_folders
            )
            success, path = create_index_note(
                self._vault_path, self._subfolder, metadata, self._use_topic_folders
            )
            if success:
                QMessageBox.information(self, "완료", f"인덱스 업데이트 완료:\n{path}")
                self.refresh()
            else:
                QMessageBox.critical(self, "오류", path)
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _open_folder(self):
        if not self._vault_path:
            return
        target = (
            str(Path(self._vault_path) / self._subfolder)
            if self._subfolder else self._vault_path
        )
        self._reveal_in_os(target, is_folder=True)
