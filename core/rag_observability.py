"""
rag_observability.py + context_compressor.py — ROS v5.0
=========================================================
Two engines in one file:

A. ContextCompressor:
   "Prefer compressed semantic abstractions over raw note injection."
   - Abstraction-aware summarization
   - Theorem compression
   - Lineage summarization
   - Contradiction clustering
   - Graph condensation

B. RAGObservability:
   "Continuously monitor retrieval precision, waste, token efficiency."
   - Retrieval precision tracking
   - Token-per-insight ratio
   - Embedding duplication rate
   - Context redundancy ratio
   - Graph traversal latency
   - Retrieval entropy
"""

from __future__ import annotations

import json
import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = _get_logger("ROS.RAGObs")


# ══════════════════════════════════════════════════════════════════════════════
# A. Context Compressor
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CompressionResult:
    original_tokens:    int
    compressed_tokens:  int
    compression_ratio:  float
    method:             str
    compressed_text:    str
    abstractions_kept:  int = 0
    equations_kept:     int = 0
    links_kept:         int = 0


class ContextCompressor:
    """
    적응형 컨텍스트 압축기.
    원시 노트 주입 대신 압축된 의미 추상화 선호.
    """

    # 압축 목표 비율
    TARGET_COMPRESSION = 0.4   # 원본의 40%로 압축

    # 보존 우선순위 패턴
    HIGH_VALUE_PATTERNS = [
        r'\$[^$]+\$',                          # LaTeX 인라인 수식
        r'\$\$[^$]+\$\$',                      # LaTeX 블록 수식
        r'\[\[[^\]]+\]\]',                     # WikiLink
        r'(?:DML|IV|DID|RDD|OLS|GMM|CATE|ATE|2SLS|LATE|ATT)',  # 방법론 키워드
        r'(?:Assumption|Theorem|Lemma|Proposition|Corollary)',   # 수학 구조
        r'(?:identification|estimator|causal|treatment|outcome)', # 인과추론 키워드
    ]

    def compress(
        self,
        text: str,
        target_tokens: int = 500,
        method: str = "auto",
    ) -> CompressionResult:
        """
        텍스트를 목표 토큰 수로 압축.
        method: "auto" | "abstract" | "theorem" | "lineage" | "graph"
        """
        original_tokens = len(text) // 4

        if original_tokens <= target_tokens:
            return CompressionResult(
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
                method="no_compression_needed",
                compressed_text=text,
            )

        if method == "auto":
            method = self._select_method(text)

        if method == "theorem":
            compressed = self._theorem_compression(text, target_tokens)
        elif method == "lineage":
            compressed = self._lineage_summarization(text, target_tokens)
        elif method == "graph":
            compressed = self._graph_condensation(text, target_tokens)
        else:
            compressed = self._abstraction_aware_summarization(text, target_tokens)

        compressed_tokens = len(compressed) // 4

        # 보존된 고가치 요소 카운트
        equations = len(re.findall(r'\$[^$]+\$', compressed))
        links = len(re.findall(r'\[\[[^\]]+\]\]', compressed))

        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / max(original_tokens, 1),
            method=method,
            compressed_text=compressed,
            equations_kept=equations,
            links_kept=links,
        )

    def compress_batch(
        self,
        texts: list[str],
        total_token_budget: int,
    ) -> list[CompressionResult]:
        """
        여러 텍스트를 총 토큰 예산 내에서 압축.
        중요도 기반으로 예산 배분.
        """
        if not texts:
            return []

        # 각 텍스트의 중요도 점수 계산
        scores = [self._importance_score(t) for t in texts]
        total_score = sum(scores) or 1.0

        results = []
        for text, score in zip(texts, scores):
            allocated = int(total_token_budget * score / total_score)
            allocated = max(allocated, 50)  # 최소 50토큰
            results.append(self.compress(text, target_tokens=allocated))

        return results

    def _select_method(self, text: str) -> str:
        """텍스트 특성에 따라 압축 방법 자동 선택."""
        # 수식이 많으면 theorem 압축
        if len(re.findall(r'\$[^$]+\$', text)) > 3:
            return "theorem"
        # WikiLink가 많으면 graph 압축
        if len(re.findall(r'\[\[[^\]]+\]\]', text)) > 5:
            return "graph"
        # 계보 관련 내용이면 lineage 압축
        if any(k in text.lower() for k in ["parent", "derived", "extends", "lineage", "origin"]):
            return "lineage"
        return "abstract"

    def _abstraction_aware_summarization(self, text: str, target_tokens: int) -> str:
        """추상화 인식 요약: 고가치 요소 보존, 저가치 서술 제거."""
        lines = text.split('\n')
        scored_lines = []

        for line in lines:
            score = self._line_importance(line)
            scored_lines.append((score, line))

        # 점수 내림차순 정렬 후 예산 내 선택
        scored_lines.sort(key=lambda x: x[0], reverse=True)
        selected = []
        used_tokens = 0

        for score, line in scored_lines:
            line_tokens = len(line) // 4 + 1
            if used_tokens + line_tokens > target_tokens:
                break
            selected.append((score, line))
            used_tokens += line_tokens

        # 원래 순서로 복원
        original_order = {line: score for score, line in scored_lines}
        selected_lines = sorted(selected, key=lambda x: lines.index(x[1]) if x[1] in lines else 0)

        return '\n'.join(line for _, line in selected_lines)

    def _theorem_compression(self, text: str, target_tokens: int) -> str:
        """수식/정리 중심 압축: 수식과 가정만 보존."""
        preserved = []
        lines = text.split('\n')

        # 수식 블록 추출
        in_math_block = False
        for line in lines:
            if '$$' in line:
                in_math_block = not in_math_block
                preserved.append(line)
            elif in_math_block:
                preserved.append(line)
            elif re.search(r'\$[^$]+\$', line):
                preserved.append(line)
            elif any(k in line for k in ['Assumption', 'Theorem', 'Lemma', 'Proof', 'QED']):
                preserved.append(line)
            elif line.startswith('#'):
                preserved.append(line)

        result = '\n'.join(preserved)
        if len(result) // 4 > target_tokens:
            result = result[:target_tokens * 4]
        return result

    def _lineage_summarization(self, text: str, target_tokens: int) -> str:
        """계보 요약: 핵심 관계와 변환만 보존."""
        lines = text.split('\n')
        preserved = []
        lineage_keywords = ['parent', 'child', 'derived', 'extends', 'origin',
                            'lineage', '→', '←', 'builds on', 'contradicts']

        for line in lines:
            if any(k in line.lower() for k in lineage_keywords):
                preserved.append(line)
            elif re.search(r'\[\[[^\]]+\]\]', line):
                preserved.append(line)
            elif line.startswith('#'):
                preserved.append(line)

        result = '\n'.join(preserved)
        if len(result) // 4 > target_tokens:
            result = result[:target_tokens * 4]
        return result

    def _graph_condensation(self, text: str, target_tokens: int) -> str:
        """그래프 응축: WikiLink 네트워크만 추출."""
        # 모든 WikiLink 추출
        links = re.findall(r'\[\[([^\]]+)\]\]', text)
        # 헤더 추출
        headers = re.findall(r'^#{1,3} .+', text, re.MULTILINE)

        condensed_parts = []
        if headers:
            condensed_parts.append("## Structure\n" + '\n'.join(headers[:5]))
        if links:
            unique_links = list(dict.fromkeys(links))[:20]
            condensed_parts.append("## Links\n" + ', '.join(f'[[{l}]]' for l in unique_links))

        result = '\n\n'.join(condensed_parts)
        if len(result) // 4 > target_tokens:
            result = result[:target_tokens * 4]
        return result

    def _line_importance(self, line: str) -> float:
        """라인 중요도 점수 계산."""
        score = 0.0
        # 헤더
        if line.startswith('###'):
            score += 0.6
        elif line.startswith('##'):
            score += 0.7
        elif line.startswith('#'):
            score += 0.8
        # 수식
        if re.search(r'\$[^$]+\$', line):
            score += 0.5
        # WikiLink
        if re.search(r'\[\[[^\]]+\]\]', line):
            score += 0.4
        # 방법론 키워드
        econ_kw = ['DML', 'IV', 'DID', 'RDD', 'OLS', 'GMM', 'CATE', 'ATE',
                   'causal', 'identification', 'assumption', 'estimator']
        score += sum(0.1 for k in econ_kw if k.lower() in line.lower())
        # 빈 줄 페널티
        if not line.strip():
            score -= 0.5
        return max(score, 0.0)

    def _importance_score(self, text: str) -> float:
        """텍스트 전체 중요도 점수."""
        score = 0.0
        score += min(len(re.findall(r'\$[^$]+\$', text)) * 0.1, 0.4)
        score += min(len(re.findall(r'\[\[[^\]]+\]\]', text)) * 0.05, 0.3)
        score += 0.3 if len(text) > 1000 else 0.1
        return max(score, 0.1)


# ══════════════════════════════════════════════════════════════════════════════
# B. RAG Observability
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RAGEvent:
    """RAG 이벤트 레코드."""
    event_type:        str   # "retrieval" | "cache_hit" | "llm_call" | "compression"
    query_hash:        str
    tokens_used:       int
    tokens_saved:      int
    latency_ms:        float
    precision_score:   float  # 검색 정밀도 (0-1)
    waste_ratio:       float  # 낭비 비율 (0-1)
    path:              str    # 인지 경로
    layer:             str    # 검색 레이어
    timestamp:         str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RAGObservability:
    """
    RAG 관측성 엔진.
    모든 RAG 작업을 지속적으로 모니터링하고 비효율 감지.
    """

    # 경고 임계값
    ALERT_THRESHOLDS = {
        "retrieval_waste_ratio":  0.6,   # 60% 이상 낭비 시 경고
        "token_per_insight":      500,   # 인사이트당 500토큰 초과 시 경고
        "embedding_dup_rate":     0.3,   # 30% 이상 중복 시 경고
        "context_redundancy":     0.5,   # 50% 이상 중복 컨텍스트 시 경고
        "avg_latency_ms":         3000,  # 3초 초과 시 경고
        "retrieval_entropy":      3.0,   # 엔트로피 3 초과 시 경고 (정밀도 낮음)
    }

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "rag_observability.json"

        # 롤링 윈도우 (최근 1000 이벤트)
        self._events: deque[RAGEvent] = deque(maxlen=1000)

        # 집계 메트릭
        self._metrics = {
            "total_retrievals":       0,
            "total_cache_hits":       0,
            "total_llm_calls":        0,
            "total_tokens_used":      0,
            "total_tokens_saved":     0,
            "total_insights":         0,
            "retrieval_waste_sum":    0.0,
            "precision_sum":          0.0,
            "latency_sum":            0.0,
            "embedding_dup_count":    0,
            "context_redundancy_sum": 0.0,
        }
        self._alerts: list[dict] = []
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._metrics.update(data.get("metrics", {}))
            except Exception:
                pass

    def _save(self):
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"metrics": self._metrics, "alert_count": len(self._alerts)}, indent=2),
                encoding="utf-8"
            )
            tmp.replace(self._path)
        except Exception:
            pass

    def record_retrieval(
        self,
        query_hash: str,
        tokens_used: int,
        tokens_saved: int,
        latency_ms: float,
        candidates_total: int,
        candidates_selected: int,
        path: str = "LOCAL_GRAPH",
        layer: str = "L3_LOCAL",
    ):
        """검색 이벤트 기록."""
        waste_ratio = 1.0 - (candidates_selected / max(candidates_total, 1))
        precision = candidates_selected / max(candidates_total, 1)

        event = RAGEvent(
            event_type="retrieval",
            query_hash=query_hash,
            tokens_used=tokens_used,
            tokens_saved=tokens_saved,
            latency_ms=latency_ms,
            precision_score=precision,
            waste_ratio=waste_ratio,
            path=path,
            layer=layer,
        )
        self._events.append(event)

        # 집계 업데이트
        self._metrics["total_retrievals"] += 1
        self._metrics["total_tokens_used"] += tokens_used
        self._metrics["total_tokens_saved"] += tokens_saved
        self._metrics["retrieval_waste_sum"] += waste_ratio
        self._metrics["precision_sum"] += precision
        self._metrics["latency_sum"] += latency_ms

        # 경고 체크
        self._check_alerts(event)

        if self._metrics["total_retrievals"] % 20 == 0:
            self._save()

    def record_cache_hit(self, query_hash: str, tokens_saved: int):
        """캐시 히트 기록."""
        self._metrics["total_cache_hits"] += 1
        self._metrics["total_tokens_saved"] += tokens_saved

    def record_llm_call(self, query_hash: str, tokens_used: int, insight_generated: bool):
        """LLM 호출 기록."""
        self._metrics["total_llm_calls"] += 1
        self._metrics["total_tokens_used"] += tokens_used
        if insight_generated:
            self._metrics["total_insights"] += 1

    def record_embedding_dup(self):
        """임베딩 중복 감지 기록."""
        self._metrics["embedding_dup_count"] += 1

    def _check_alerts(self, event: RAGEvent):
        """임계값 초과 시 경고 생성."""
        alerts = []

        if event.waste_ratio > self.ALERT_THRESHOLDS["retrieval_waste_ratio"]:
            alerts.append({
                "type": "HIGH_RETRIEVAL_WASTE",
                "value": round(event.waste_ratio, 3),
                "threshold": self.ALERT_THRESHOLDS["retrieval_waste_ratio"],
                "message": f"Retrieval waste {event.waste_ratio:.1%} exceeds threshold",
            })

        if event.latency_ms > self.ALERT_THRESHOLDS["avg_latency_ms"]:
            alerts.append({
                "type": "HIGH_LATENCY",
                "value": round(event.latency_ms, 1),
                "threshold": self.ALERT_THRESHOLDS["avg_latency_ms"],
                "message": f"Retrieval latency {event.latency_ms:.0f}ms exceeds {self.ALERT_THRESHOLDS['avg_latency_ms']}ms",
            })

        for alert in alerts:
            alert["timestamp"] = datetime.utcnow().isoformat()
            self._alerts.append(alert)
            logger.warning(f"[RAG Alert] {alert['message']}")

        # 최근 100개 알림만 유지
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]

    def get_dashboard_data(self) -> dict:
        """대시보드용 집계 데이터 반환."""
        total_ret = max(self._metrics["total_retrievals"], 1)
        total_calls = max(
            self._metrics["total_retrievals"] + self._metrics["total_llm_calls"], 1
        )
        total_insights = max(self._metrics["total_insights"], 1)

        # 토큰 당 인사이트 비율
        token_per_insight = self._metrics["total_tokens_used"] / total_insights

        # 평균 메트릭
        avg_waste = self._metrics["retrieval_waste_sum"] / total_ret
        avg_precision = self._metrics["precision_sum"] / total_ret
        avg_latency = self._metrics["latency_sum"] / total_ret

        # 캐시 히트율
        cache_hit_rate = self._metrics["total_cache_hits"] / total_calls

        # 임베딩 중복율
        emb_dup_rate = self._metrics["embedding_dup_count"] / total_ret

        # 최근 이벤트 경향 (최근 50개)
        recent = list(self._events)[-50:]
        recent_waste = sum(e.waste_ratio for e in recent) / max(len(recent), 1)
        recent_latency = sum(e.latency_ms for e in recent) / max(len(recent), 1)

        return {
            # 핵심 KPI
            "total_retrievals":     self._metrics["total_retrievals"],
            "total_cache_hits":     self._metrics["total_cache_hits"],
            "total_llm_calls":      self._metrics["total_llm_calls"],
            "total_tokens_used":    self._metrics["total_tokens_used"],
            "total_tokens_saved":   self._metrics["total_tokens_saved"],

            # 효율성 메트릭
            "cache_hit_rate":       round(cache_hit_rate, 3),
            "avg_retrieval_waste":  round(avg_waste, 3),
            "avg_precision":        round(avg_precision, 3),
            "avg_latency_ms":       round(avg_latency, 1),
            "token_per_insight":    round(token_per_insight, 1),
            "embedding_dup_rate":   round(emb_dup_rate, 3),

            # 최근 경향
            "recent_waste_trend":   round(recent_waste, 3),
            "recent_latency_trend": round(recent_latency, 1),

            # 경고
            "active_alerts":        len([a for a in self._alerts if
                                        (datetime.utcnow() - datetime.fromisoformat(a["timestamp"])).seconds < 3600]),
            "recent_alerts":        self._alerts[-5:],

            # 건강 상태
            "health_status":        self._compute_health_status(avg_waste, avg_latency, cache_hit_rate),
        }

    def _compute_health_status(
        self, waste: float, latency: float, cache_rate: float
    ) -> str:
        """RAG 시스템 건강 상태 계산."""
        score = 0
        if waste < 0.3:
            score += 2
        elif waste < 0.5:
            score += 1

        if latency < 1000:
            score += 2
        elif latency < 2000:
            score += 1

        if cache_rate > 0.3:
            score += 2
        elif cache_rate > 0.1:
            score += 1

        if score >= 5:
            return "OPTIMAL"
        elif score >= 3:
            return "HEALTHY"
        elif score >= 1:
            return "DEGRADED"
        else:
            return "CRITICAL"

    def get_efficiency_report(self) -> str:
        """인간이 읽을 수 있는 효율성 리포트 생성."""
        data = self.get_dashboard_data()
        lines = [
            "## RAG Efficiency Report",
            f"- **Health**: {data['health_status']}",
            f"- **Cache Hit Rate**: {data['cache_hit_rate']:.1%}",
            f"- **Avg Retrieval Waste**: {data['avg_retrieval_waste']:.1%}",
            f"- **Avg Precision**: {data['avg_precision']:.1%}",
            f"- **Avg Latency**: {data['avg_latency_ms']:.0f}ms",
            f"- **Token/Insight**: {data['token_per_insight']:.0f}",
            f"- **Tokens Saved**: {data['total_tokens_saved']:,}",
            f"- **Active Alerts**: {data['active_alerts']}",
        ]
        return '\n'.join(lines)

    def identify_expensive_patterns(self) -> list[dict]:
        """비용이 높은 패턴 식별."""
        patterns = []
        recent = list(self._events)[-100:]

        # 고지연 패턴
        high_latency = [e for e in recent if e.latency_ms > 2000]
        if high_latency:
            patterns.append({
                "pattern": "HIGH_LATENCY_RETRIEVALS",
                "count": len(high_latency),
                "avg_latency": sum(e.latency_ms for e in high_latency) / len(high_latency),
                "recommendation": "Enable more aggressive caching or reduce retrieval depth",
            })

        # 고낭비 패턴
        high_waste = [e for e in recent if e.waste_ratio > 0.7]
        if high_waste:
            patterns.append({
                "pattern": "HIGH_RETRIEVAL_WASTE",
                "count": len(high_waste),
                "avg_waste": sum(e.waste_ratio for e in high_waste) / len(high_waste),
                "recommendation": "Tighten retrieval radius or increase MIN_COMPOSITE_SCORE",
            })

        return patterns


# ══════════════════════════════════════════════════════════════════════════════
# Singletons
# ══════════════════════════════════════════════════════════════════════════════

_compressor: Optional[ContextCompressor] = None
_observability: Optional[RAGObservability] = None


def get_context_compressor() -> ContextCompressor:
    global _compressor
    if _compressor is None:
        _compressor = ContextCompressor()
    return _compressor


def get_rag_observability() -> RAGObservability:
    global _observability
    if _observability is None:
        _observability = RAGObservability()
    return _observability
