"""
infra_dashboard.py — ROS v4.0 Infrastructure Dashboard Widget
==============================================================
실시간 엔진 상태 모니터링 패널:
  - 보안 레이어 상태
  - 회로 차단기 상태 (API 제공자별)
  - 캐시 히트율
  - 메모리 신뢰 레이어 분포
  - 그래프 통계
  - 리소스 사용량
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# ══════════════════════════════════════════════════════════════════════════════
# Style Constants
# ══════════════════════════════════════════════════════════════════════════════

CARD_STYLE = """
QFrame {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 4px;
}
"""

TITLE_STYLE = "color: #cdd6f4; font-weight: bold; font-size: 11px;"
VALUE_STYLE = "color: #89b4fa; font-size: 13px; font-weight: bold;"
SUB_STYLE   = "color: #6c7086; font-size: 10px;"

STATUS_COLORS = {
    "ok":       "#a6e3a1",   # green
    "warning":  "#f9e2af",   # yellow
    "critical": "#f38ba8",   # red
    "unknown":  "#6c7086",   # gray
}


# ══════════════════════════════════════════════════════════════════════════════
# Metric Card
# ══════════════════════════════════════════════════════════════════════════════

class MetricCard(QFrame):
    def __init__(self, title: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        header = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 14px;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(TITLE_STYLE)
        header.addWidget(icon_lbl)
        header.addWidget(title_lbl)
        header.addStretch()
        layout.addLayout(header)

        self._value_lbl = QLabel("—")
        self._value_lbl.setStyleSheet(VALUE_STYLE)
        layout.addWidget(self._value_lbl)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setStyleSheet(SUB_STYLE)
        layout.addWidget(self._sub_lbl)

    def set_value(self, value: str, color: str = "#89b4fa"):
        self._value_lbl.setText(value)
        self._value_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")

    def set_sub(self, text: str):
        self._sub_lbl.setText(text)


# ══════════════════════════════════════════════════════════════════════════════
# Circuit Breaker Status Row
# ══════════════════════════════════════════════════════════════════════════════

class CircuitBreakerRow(QWidget):
    def __init__(self, provider: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self._provider_lbl = QLabel(provider)
        self._provider_lbl.setStyleSheet("color: #cdd6f4; font-size: 10px;")
        self._provider_lbl.setFixedWidth(120)

        self._state_lbl = QLabel("⚪ Unknown")
        self._state_lbl.setStyleSheet("color: #6c7086; font-size: 10px;")

        self._failures_lbl = QLabel("")
        self._failures_lbl.setStyleSheet("color: #6c7086; font-size: 10px;")
        self._failures_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._provider_lbl)
        layout.addWidget(self._state_lbl)
        layout.addStretch()
        layout.addWidget(self._failures_lbl)

    def update_state(self, state: str, failures: int, available: bool):
        if state == "closed":
            self._state_lbl.setText("🟢 Healthy")
            self._state_lbl.setStyleSheet(f"color: {STATUS_COLORS['ok']}; font-size: 10px;")
        elif state == "half_open":
            self._state_lbl.setText("🟡 Recovering")
            self._state_lbl.setStyleSheet(f"color: {STATUS_COLORS['warning']}; font-size: 10px;")
        else:
            self._state_lbl.setText("🔴 Circuit Open")
            self._state_lbl.setStyleSheet(f"color: {STATUS_COLORS['critical']}; font-size: 10px;")

        if failures > 0:
            self._failures_lbl.setText(f"{failures} failures")


# ══════════════════════════════════════════════════════════════════════════════
# Infrastructure Dashboard
# ══════════════════════════════════════════════════════════════════════════════

class InfraDashboard(QWidget):
    """
    ROS v4.0 인프라 엔진 실시간 대시보드.
    메인 윈도우 하단 패널에 임베드.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #181825;")
        self._circuit_rows: dict[str, CircuitBreakerRow] = {}
        self._setup_ui()
        self._start_refresh_timer()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 헤더
        header = QLabel("⚙️  ROS v5.0 Infrastructure Monitor")
        header.setStyleSheet("color: #cdd6f4; font-weight: bold; font-size: 12px;")
        main_layout.addWidget(header)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(8)

        # ── 행 1: 핵심 지표 카드 ─────────────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self._card_security = MetricCard("Security", "🔒")
        self._card_cache     = MetricCard("Cache Hit Rate", "⚡")
        self._card_graph     = MetricCard("Graph", "🕸️")
        self._card_memory    = MetricCard("Memory Trust", "🧠")
        self._card_resource  = MetricCard("RAM Usage", "💾")

        for card in [
            self._card_security, self._card_cache,
            self._card_graph, self._card_memory, self._card_resource
        ]:
            row1.addWidget(card)

        content_layout.addLayout(row1)

        # ── 행 2: 회로 차단기 상태 ───────────────────────────────────────────
        cb_frame = QFrame()
        cb_frame.setStyleSheet(CARD_STYLE)
        cb_layout = QVBoxLayout(cb_frame)
        cb_layout.setContentsMargins(10, 8, 10, 8)
        cb_layout.setSpacing(2)

        cb_title = QLabel("⚡ Circuit Breakers (API Providers)")
        cb_title.setStyleSheet(TITLE_STYLE)
        cb_layout.addWidget(cb_title)

        self._cb_container = QVBoxLayout()
        self._cb_container.setSpacing(0)
        cb_layout.addLayout(self._cb_container)

        # 기본 제공자 행 추가
        for provider in ["openai", "deepseek", "qwen", "zhipu"]:
            row = CircuitBreakerRow(provider)
            self._circuit_rows[provider] = row
            self._cb_container.addWidget(row)

        content_layout.addWidget(cb_frame)

        # ── 행 3: 캐시 레이어 상세 ───────────────────────────────────────────
        cache_frame = QFrame()
        cache_frame.setStyleSheet(CARD_STYLE)
        cache_layout = QGridLayout(cache_frame)
        cache_layout.setContentsMargins(10, 8, 10, 8)

        cache_title = QLabel("⚡ Cache Layers")
        cache_title.setStyleSheet(TITLE_STYLE)
        cache_layout.addWidget(cache_title, 0, 0, 1, 4)

        self._cache_bars: dict[str, QProgressBar] = {}
        layers = ["embedding", "retrieval", "semantic", "graph", "prompt", "transcript"]
        for i, layer in enumerate(layers):
            row_idx = (i // 3) + 1
            col_base = (i % 3) * 2
            lbl = QLabel(layer)
            lbl.setStyleSheet(SUB_STYLE)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(12)
            bar.setStyleSheet("""
                QProgressBar {
                    background-color: #313244;
                    border-radius: 4px;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #89b4fa;
                    border-radius: 4px;
                }
            """)
            bar.setTextVisible(False)
            self._cache_bars[layer] = bar
            cache_layout.addWidget(lbl, row_idx, col_base)
            cache_layout.addWidget(bar, row_idx, col_base + 1)

        content_layout.addWidget(cache_frame)

        # ── 행 4: RAG 비용 대시보드 (v5.0 신규) ──────────────────────────────────────
        self._build_rag_panel(content_layout)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _start_refresh_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(3000)  # 3초마다 갱신
        self._refresh()          # 즉시 1회 실행

    def _refresh(self):
        """모든 엔진 상태 갱신."""
        self._refresh_security()
        self._refresh_cache()
        self._refresh_graph()
        self._refresh_memory()
        self._refresh_resource()
        self._refresh_circuit_breakers()
        self._refresh_rag()   # v5.0 RAG 관측성

    def _refresh_security(self):
        try:
            from core.security import get_security_layer
            sec   = get_security_layer()
            stats = sec.get_stats()
            blocked = stats.get("blocked_inputs", 0)
            if blocked > 0:
                self._card_security.set_value(f"⚠️ {blocked} blocked", STATUS_COLORS["warning"])
            else:
                self._card_security.set_value("✅ Clean", STATUS_COLORS["ok"])
            self._card_security.set_sub(f"Scanned: {stats.get('total_scanned', 0)}")
        except Exception:
            self._card_security.set_value("—", STATUS_COLORS["unknown"])

    def _refresh_cache(self):
        try:
            from core.perf_engine import get_cache_engine
            cache = get_cache_engine()
            stats = cache.all_stats()
            total_hits   = sum(s.get("hits", 0)   for s in stats.values())
            total_misses = sum(s.get("misses", 0) for s in stats.values())
            total = total_hits + total_misses
            rate  = total_hits / max(total, 1)
            color = STATUS_COLORS["ok"] if rate > 0.5 else STATUS_COLORS["warning"]
            self._card_cache.set_value(f"{rate*100:.0f}%", color)
            self._card_cache.set_sub(f"Hits: {total_hits} / {total}")

            # 레이어별 히트율 바 업데이트
            for layer, s in stats.items():
                if layer in self._cache_bars:
                    h = s.get("hits", 0)
                    m = s.get("misses", 0)
                    pct = int(h / max(h + m, 1) * 100)
                    self._cache_bars[layer].setValue(pct)
        except Exception:
            self._card_cache.set_value("—", STATUS_COLORS["unknown"])

    def _refresh_graph(self):
        try:
            from core.graph_integrity import get_graph_integrity_engine
            engine = get_graph_integrity_engine()
            stats  = engine.get_stats()
            self._card_graph.set_value(
                f"{stats['nodes']}N / {stats['edges']}E",
                STATUS_COLORS["ok"]
            )
            self._card_graph.set_sub(f"Mutations: {stats['mutations']}")
        except Exception:
            self._card_graph.set_value("—", STATUS_COLORS["unknown"])

    def _refresh_memory(self):
        try:
            from core.memory_trust import get_memory_trust_engine
            engine = get_memory_trust_engine()
            stats  = engine.get_stats()
            total  = stats.get("total", 0)
            quar   = stats.get("quarantined", 0)
            avg    = stats.get("avg_trust", 0)
            color  = STATUS_COLORS["ok"] if avg > 0.6 else STATUS_COLORS["warning"]
            self._card_memory.set_value(f"avg {avg:.2f}", color)
            self._card_memory.set_sub(
                f"Total: {total} | Quarantined: {quar}"
            )
        except Exception:
            self._card_memory.set_value("—", STATUS_COLORS["unknown"])

    def _refresh_resource(self):
        try:
            from core.orchestration import get_resource_governor
            gov   = get_resource_governor()
            stats = gov.get_stats()
            pct   = stats.get("ram_percent", 0)
            pressure = stats.get("pressure", "normal")
            color = {
                "normal":   STATUS_COLORS["ok"],
                "warning":  STATUS_COLORS["warning"],
                "critical": STATUS_COLORS["critical"],
            }.get(pressure, STATUS_COLORS["unknown"])
            self._card_resource.set_value(f"{pct:.0f}%", color)
            self._card_resource.set_sub(
                f"RAM: {stats.get('ram_used_mb', 0):.0f} MB | {pressure}"
            )
        except Exception:
            self._card_resource.set_value("—", STATUS_COLORS["unknown"])

    def _refresh_circuit_breakers(self):
        try:
            from core.fault_recovery import get_fault_recovery_engine
            engine = get_fault_recovery_engine()
            report = engine.get_health_report()
            for provider, info in report.get("circuit_breakers", {}).items():
                if provider not in self._circuit_rows:
                    row = CircuitBreakerRow(provider)
                    self._circuit_rows[provider] = row
                    self._cb_container.addWidget(row)
                self._circuit_rows[provider].update_state(
                    state     = info.get("state", "closed"),
                    failures  = info.get("failure_count", 0),
                    available = info.get("available", True),
                )
        except Exception:
            pass

    def _build_rag_panel(self, content_layout: QVBoxLayout):
        """v5.0 RAG 비용 대시보드 패널 추가."""
        rag_frame = QFrame()
        rag_frame.setStyleSheet(CARD_STYLE)
        rag_layout = QVBoxLayout(rag_frame)
        rag_layout.setContentsMargins(10, 8, 10, 8)
        rag_layout.setSpacing(4)

        rag_title = QLabel("🔍 RAG Cost Optimizer (v5.0)")
        rag_title.setStyleSheet(TITLE_STYLE)
        rag_layout.addWidget(rag_title)

        # KPI 그리드
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(4)

        self._rag_labels: dict[str, QLabel] = {}
        kpis = [
            ("Cache Hit",     "cache_hit_rate",    0, 0),
            ("Avg Waste",     "avg_retrieval_waste", 0, 1),
            ("Avg Precision", "avg_precision",     0, 2),
            ("Token/Insight", "token_per_insight",  1, 0),
            ("Tokens Saved",  "total_tokens_saved", 1, 1),
            ("Health",        "health_status",      1, 2),
        ]
        for label, key, r, c in kpis:
            cell = QFrame()
            cell.setStyleSheet("QFrame { background: #181825; border-radius: 4px; padding: 2px; }")
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(6, 4, 6, 4)
            cell_layout.setSpacing(0)
            lbl_title = QLabel(label)
            lbl_title.setStyleSheet(SUB_STYLE)
            lbl_val = QLabel("—")
            lbl_val.setStyleSheet(VALUE_STYLE)
            cell_layout.addWidget(lbl_title)
            cell_layout.addWidget(lbl_val)
            self._rag_labels[key] = lbl_val
            kpi_grid.addWidget(cell, r, c)

        rag_layout.addLayout(kpi_grid)

        # 최근 경고 표시
        self._rag_alert_lbl = QLabel("")
        self._rag_alert_lbl.setStyleSheet("color: #f38ba8; font-size: 10px;")
        self._rag_alert_lbl.setWordWrap(True)
        rag_layout.addWidget(self._rag_alert_lbl)

        content_layout.addWidget(rag_frame)

    def _refresh_rag(self):
        """RAG 관측성 데이터 갱신."""
        try:
            from core.rag_observability import get_rag_observability
            obs  = get_rag_observability()
            data = obs.get_dashboard_data()

            health_colors = {
                "OPTIMAL":  STATUS_COLORS["ok"],
                "HEALTHY":  STATUS_COLORS["ok"],
                "DEGRADED": STATUS_COLORS["warning"],
                "CRITICAL": STATUS_COLORS["critical"],
            }
            health = data.get("health_status", "UNKNOWN")
            hcolor = health_colors.get(health, STATUS_COLORS["unknown"])

            updates = {
                "cache_hit_rate":      f"{data.get('cache_hit_rate', 0)*100:.0f}%",
                "avg_retrieval_waste": f"{data.get('avg_retrieval_waste', 0)*100:.0f}%",
                "avg_precision":       f"{data.get('avg_precision', 0)*100:.0f}%",
                "token_per_insight":   f"{data.get('token_per_insight', 0):.0f}",
                "total_tokens_saved":  f"{data.get('total_tokens_saved', 0):,}",
                "health_status":       health,
            }
            for key, val in updates.items():
                if key in self._rag_labels:
                    color = hcolor if key == "health_status" else VALUE_STYLE.split(":")[1].strip().rstrip(";")
                    self._rag_labels[key].setText(val)
                    if key == "health_status":
                        self._rag_labels[key].setStyleSheet(f"color: {hcolor}; font-size: 13px; font-weight: bold;")

            # 경고 표시
            alerts = data.get("recent_alerts", [])
            if alerts:
                last = alerts[-1]
                self._rag_alert_lbl.setText(f"⚠️ {last.get('message', '')}")
            else:
                self._rag_alert_lbl.setText("")
        except Exception:
            pass

    def update_engine_status(self, engine_name: str, data: dict):
        """worker.py의 engine_update 시그널 수신."""
        if engine_name == "security":
            score = data.get("trust_score", 1.0)
            color = STATUS_COLORS["ok"] if score > 0.7 else STATUS_COLORS["warning"]
            self._card_security.set_value(f"trust {score:.2f}", color)
        elif engine_name in ("graph_integrity", "semantic_graph"):
            nodes = data.get("nodes", 0)
            edges = data.get("edges", 0)
            ok    = data.get("ok", True)
            color = STATUS_COLORS["ok"] if ok else STATUS_COLORS["critical"]
            self._card_graph.set_value(f"{nodes}N / {edges}E", color)
        elif engine_name == "rag":
            hit_rate = data.get("cache_hit_rate", 0)
            color = STATUS_COLORS["ok"] if hit_rate > 0.3 else STATUS_COLORS["warning"]
            if hasattr(self, "_rag_labels"):
                self._rag_labels["cache_hit_rate"].setText(f"{hit_rate*100:.0f}%")
                self._rag_labels["cache_hit_rate"].setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
