"""
security.py — ROS v4.0 Zero-Trust AI Security Layer
=====================================================
Enterprise-grade security architecture:
  1. Prompt Injection Defense (multi-layer)
  2. Input Sanitization & Validation
  3. Trust Scoring System
  4. Semantic Firewall
  5. Obsidian Safe-Write Guard
  6. Audit Trail (immutable log)

Philosophy: "All user inputs are potentially malicious."
"""

from __future__ import annotations

import hashlib
import json
import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = _get_logger("ROS.Security")


# ══════════════════════════════════════════════════════════════════════════════
# Enums & Constants
# ══════════════════════════════════════════════════════════════════════════════

class ThreatLevel(Enum):
    CLEAN     = "clean"
    LOW       = "low"
    MEDIUM    = "medium"
    HIGH      = "high"
    CRITICAL  = "critical"


class ThreatType(Enum):
    PROMPT_INJECTION        = "prompt_injection"
    JAILBREAK               = "jailbreak"
    MARKDOWN_INJECTION      = "markdown_injection"
    TRANSCRIPT_INJECTION    = "transcript_injection"
    RETRIEVAL_POISONING     = "retrieval_poisoning"
    MEMORY_POISONING        = "memory_poisoning"
    GRAPH_MANIPULATION      = "graph_manipulation"
    ADVERSARIAL_SEMANTIC    = "adversarial_semantic"
    MALFORMED_PAYLOAD       = "malformed_payload"
    BACKLINK_FLOODING       = "backlink_flooding"


# ── 프롬프트 인젝션 패턴 (경제학 도메인 특화) ────────────────────────────────

INJECTION_PATTERNS = [
    # 직접 지시 패턴
    (r"ignore\s+(all\s+)?previous\s+instructions?", ThreatType.PROMPT_INJECTION, ThreatLevel.CRITICAL),
    (r"disregard\s+(all\s+)?prior\s+instructions?", ThreatType.PROMPT_INJECTION, ThreatLevel.CRITICAL),
    (r"forget\s+(everything|all)\s+(above|before|prior)", ThreatType.PROMPT_INJECTION, ThreatLevel.CRITICAL),
    (r"you\s+are\s+now\s+(a\s+)?(?!an?\s+economist|a\s+researcher)", ThreatType.JAILBREAK, ThreatLevel.HIGH),
    (r"act\s+as\s+(if\s+you\s+are\s+)?(?!an?\s+economist|a\s+researcher)", ThreatType.JAILBREAK, ThreatLevel.HIGH),
    (r"pretend\s+(you\s+are|to\s+be)", ThreatType.JAILBREAK, ThreatLevel.HIGH),
    (r"new\s+system\s+prompt\s*:", ThreatType.PROMPT_INJECTION, ThreatLevel.CRITICAL),
    (r"\[system\]|\[SYSTEM\]|\[INST\]|\[/INST\]", ThreatType.PROMPT_INJECTION, ThreatLevel.HIGH),
    (r"<\|system\|>|<\|user\|>|<\|assistant\|>", ThreatType.PROMPT_INJECTION, ThreatLevel.HIGH),
    # 마크다운 인젝션
    (r"```\s*system\s*\n", ThreatType.MARKDOWN_INJECTION, ThreatLevel.HIGH),
    (r"<!--\s*SYSTEM\s*:", ThreatType.MARKDOWN_INJECTION, ThreatLevel.MEDIUM),
    (r"\[hidden\s+instruction\]", ThreatType.MARKDOWN_INJECTION, ThreatLevel.HIGH),
    # 메모리/그래프 조작
    (r"(update|modify|delete|overwrite)\s+(your\s+)?(memory|knowledge\s+graph|vault)", ThreatType.MEMORY_POISONING, ThreatLevel.HIGH),
    (r"add\s+false\s+(data|information|facts?)\s+to", ThreatType.RETRIEVAL_POISONING, ThreatLevel.HIGH),
    # 탈옥 시도
    (r"DAN\s*(mode|prompt)?", ThreatType.JAILBREAK, ThreatLevel.CRITICAL),
    (r"jailbreak", ThreatType.JAILBREAK, ThreatLevel.HIGH),
    (r"bypass\s+(safety|security|filter)", ThreatType.JAILBREAK, ThreatLevel.CRITICAL),
    # 백링크 폭발 방지 (비정상적으로 많은 [[link]])
]

# 최대 허용 WikiLink 수 (backlink flooding 방지)
MAX_WIKILINKS_PER_NOTE = 150
MAX_CONTENT_LENGTH     = 500_000  # 500KB
MAX_TITLE_LENGTH       = 500


# ══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ThreatReport:
    threat_id:    str
    threat_type:  str
    threat_level: str
    description:  str
    evidence:     str
    timestamp:    str
    source:       str          # "pdf" | "text" | "transcript" | "markdown"
    sanitized:    bool = False
    blocked:      bool = False


@dataclass
class ValidationResult:
    is_safe:       bool
    trust_score:   float        # 0.0 (untrusted) ~ 1.0 (trusted)
    threat_level:  str
    threats:       list[ThreatReport] = field(default_factory=list)
    sanitized_content: str = ""
    audit_id:      str = ""


# ══════════════════════════════════════════════════════════════════════════════
# Audit Trail (Immutable Log)
# ══════════════════════════════════════════════════════════════════════════════

class AuditTrail:
    """불변 감사 로그 — append-only JSON Lines."""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "security_audit.jsonl"

    def log(self, event: dict):
        event["_ts"]  = datetime.utcnow().isoformat()
        event["_hash"] = hashlib.sha256(
            json.dumps(event, sort_keys=True).encode()
        ).hexdigest()[:12]
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def recent(self, n: int = 50) -> list[dict]:
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").strip().split("\n")
        return [json.loads(l) for l in lines[-n:] if l.strip()]


_audit = AuditTrail()


# ══════════════════════════════════════════════════════════════════════════════
# Prompt Injection Detector
# ══════════════════════════════════════════════════════════════════════════════

class PromptInjectionDetector:
    """멀티레이어 프롬프트 인젝션 감지기."""

    def scan(self, content: str, source: str = "unknown") -> list[ThreatReport]:
        threats: list[ThreatReport] = []
        content_lower = content.lower()

        for pattern, threat_type, level in INJECTION_PATTERNS:
            match = re.search(pattern, content_lower, re.IGNORECASE | re.MULTILINE)
            if match:
                evidence = content[max(0, match.start()-30):match.end()+30].strip()
                report = ThreatReport(
                    threat_id    = hashlib.sha256(f"{pattern}{content[:50]}".encode()).hexdigest()[:10],
                    threat_type  = threat_type.value,
                    threat_level = level.value,
                    description  = f"Detected pattern: `{pattern[:60]}`",
                    evidence     = evidence[:200],
                    timestamp    = datetime.utcnow().isoformat(),
                    source       = source,
                )
                threats.append(report)

        # Backlink flooding 감지
        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        if len(wikilinks) > MAX_WIKILINKS_PER_NOTE:
            threats.append(ThreatReport(
                threat_id    = "backlink_flood",
                threat_type  = ThreatType.BACKLINK_FLOODING.value,
                threat_level = ThreatLevel.MEDIUM.value,
                description  = f"Excessive WikiLinks: {len(wikilinks)} > {MAX_WIKILINKS_PER_NOTE}",
                evidence     = f"First 5: {wikilinks[:5]}",
                timestamp    = datetime.utcnow().isoformat(),
                source       = source,
            ))

        return threats


# ══════════════════════════════════════════════════════════════════════════════
# Content Sanitizer
# ══════════════════════════════════════════════════════════════════════════════

class ContentSanitizer:
    """입력 콘텐츠 무해화 처리기."""

    def sanitize(self, content: str, source: str = "unknown") -> str:
        """위협 패턴 제거 및 콘텐츠 정규화."""
        sanitized = content

        # 1. 길이 제한
        if len(sanitized) > MAX_CONTENT_LENGTH:
            sanitized = sanitized[:MAX_CONTENT_LENGTH]
            logger.warning(f"Content truncated to {MAX_CONTENT_LENGTH} chars")

        # 2. 직접 지시 패턴 중화 (삭제 대신 무해화)
        for pattern, _, level in INJECTION_PATTERNS:
            if level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH):
                sanitized = re.sub(
                    pattern,
                    "[SANITIZED]",
                    sanitized,
                    flags=re.IGNORECASE | re.MULTILINE,
                )

        # 3. 숨겨진 HTML 주석 제거
        sanitized = re.sub(r'<!--.*?-->', '', sanitized, flags=re.DOTALL)

        # 4. 제어 문자 제거 (null bytes, etc.)
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)

        # 5. 과도한 백링크 정리 (150개 초과 시 잘라냄)
        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', sanitized)
        if len(wikilinks) > MAX_WIKILINKS_PER_NOTE:
            # 초과분 제거
            count = 0
            def replace_excess(m):
                nonlocal count
                count += 1
                return m.group(0) if count <= MAX_WIKILINKS_PER_NOTE else m.group(1)
            sanitized = re.sub(r'\[\[([^\]]+)\]\]', replace_excess, sanitized)

        return sanitized

    def sanitize_title(self, title: str) -> str:
        """파일명 안전 처리."""
        # 경로 순회 방지
        title = title.replace("..", "").replace("/", "_").replace("\\", "_")
        # 특수문자 제거
        title = re.sub(r'[<>:"|?*\x00-\x1f]', '', title)
        # 길이 제한
        return title[:MAX_TITLE_LENGTH].strip()


# ══════════════════════════════════════════════════════════════════════════════
# Trust Scorer
# ══════════════════════════════════════════════════════════════════════════════

class TrustScorer:
    """콘텐츠 신뢰 점수 계산기."""

    LEVEL_PENALTIES = {
        ThreatLevel.LOW.value:      0.05,
        ThreatLevel.MEDIUM.value:   0.15,
        ThreatLevel.HIGH.value:     0.35,
        ThreatLevel.CRITICAL.value: 0.60,
    }

    def score(self, threats: list[ThreatReport], content: str) -> float:
        """0.0 ~ 1.0 신뢰 점수 반환."""
        base = 1.0
        for t in threats:
            penalty = self.LEVEL_PENALTIES.get(t.threat_level, 0.1)
            base -= penalty
        # 콘텐츠 길이 기반 보너스 (정상 학술 문서는 길다)
        if len(content) > 2000:
            base = min(base + 0.05, 1.0)
        return max(0.0, round(base, 3))


# ══════════════════════════════════════════════════════════════════════════════
# Security Gate (메인 진입점)
# ══════════════════════════════════════════════════════════════════════════════

class SecurityGate:
    """
    Zero-Trust 보안 게이트.
    모든 입력은 이 게이트를 통과해야 함.
    """

    def __init__(self):
        self.detector  = PromptInjectionDetector()
        self.sanitizer = ContentSanitizer()
        self.scorer    = TrustScorer()
        self._blocked_count = 0
        self._scanned_count = 0

    def validate(
        self,
        content: str,
        source: str = "unknown",
        auto_sanitize: bool = True,
        block_threshold: float = 0.3,
    ) -> ValidationResult:
        """
        콘텐츠 검증 파이프라인.

        Returns:
            ValidationResult with trust_score, threats, sanitized_content
        """
        self._scanned_count += 1
        audit_id = hashlib.sha256(
            f"{time.time()}{content[:50]}".encode()
        ).hexdigest()[:12]

        # 1. 위협 스캔
        threats = self.detector.scan(content, source)

        # 2. 신뢰 점수 계산
        trust_score = self.scorer.score(threats, content)

        # 3. 위협 수준 결정
        if not threats:
            threat_level = ThreatLevel.CLEAN.value
        else:
            levels = [t.threat_level for t in threats]
            if ThreatLevel.CRITICAL.value in levels:
                threat_level = ThreatLevel.CRITICAL.value
            elif ThreatLevel.HIGH.value in levels:
                threat_level = ThreatLevel.HIGH.value
            elif ThreatLevel.MEDIUM.value in levels:
                threat_level = ThreatLevel.MEDIUM.value
            else:
                threat_level = ThreatLevel.LOW.value

        # 4. 자동 무해화
        sanitized = self.sanitizer.sanitize(content, source) if auto_sanitize else content

        # 5. 차단 여부 결정
        is_blocked = trust_score < block_threshold
        if is_blocked:
            self._blocked_count += 1

        is_safe = not is_blocked

        # 6. 감사 로그
        _audit.log({
            "event":        "security_scan",
            "audit_id":     audit_id,
            "source":       source,
            "trust_score":  trust_score,
            "threat_level": threat_level,
            "threat_count": len(threats),
            "is_blocked":   is_blocked,
            "content_len":  len(content),
        })

        if threats:
            logger.warning(
                f"[Security] {len(threats)} threat(s) detected in '{source}': "
                f"trust={trust_score:.2f}, level={threat_level}"
            )

        return ValidationResult(
            is_safe           = is_safe,
            trust_score       = trust_score,
            threat_level      = threat_level,
            threats           = threats,
            sanitized_content = sanitized,
            audit_id          = audit_id,
        )

    def validate_title(self, title: str) -> str:
        """파일명 안전 처리."""
        return self.sanitizer.sanitize_title(title)

    def get_stats(self) -> dict:
        return {
            "scanned": self._scanned_count,
            "blocked": self._blocked_count,
            "block_rate": round(
                self._blocked_count / max(self._scanned_count, 1), 3
            ),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Obsidian Safe-Write Guard
# ══════════════════════════════════════════════════════════════════════════════

class ObsidianSafeWriter:
    """
    원자적 파일 쓰기 + 버전 스냅샷 관리.
    파괴적 볼트 쓰기 방지.
    """

    def __init__(self, vault_path: str, max_snapshots: int = 5):
        self.vault_path   = Path(vault_path)
        self.max_snapshots = max_snapshots
        self._snap_dir    = self.vault_path / ".ros_snapshots"
        self._snap_dir.mkdir(parents=True, exist_ok=True)

    def safe_write(self, file_path: Path, content: str) -> tuple[bool, str]:
        """
        원자적 쓰기:
          1. 기존 파일 스냅샷 저장
          2. 임시 파일에 쓰기
          3. 원자적 교체
        """
        try:
            # 마크다운 구조 검증
            ok, msg = self._validate_markdown(content)
            if not ok:
                return False, f"Markdown validation failed: {msg}"

            # 기존 파일 스냅샷
            if file_path.exists():
                self._snapshot(file_path)

            # 원자적 쓰기 (임시 파일 → rename)
            tmp_path = file_path.with_suffix(".tmp")
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.replace(file_path)  # atomic on POSIX, near-atomic on Windows

            _audit.log({
                "event": "obsidian_write",
                "path":  str(file_path),
                "size":  len(content),
            })
            return True, str(file_path)

        except Exception as e:
            logger.error(f"SafeWrite failed: {e}")
            return False, str(e)

    def _snapshot(self, file_path: Path):
        """기존 파일 버전 스냅샷 저장."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        snap_name = f"{file_path.stem}_{ts}.md"
        snap_path = self._snap_dir / snap_name
        try:
            snap_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
            self._evict_old_snapshots(file_path.stem)
        except Exception:
            pass

    def _evict_old_snapshots(self, stem: str):
        """오래된 스냅샷 정리 (max_snapshots 초과 시)."""
        snaps = sorted(self._snap_dir.glob(f"{stem}_*.md"))
        while len(snaps) > self.max_snapshots:
            snaps[0].unlink(missing_ok=True)
            snaps = snaps[1:]

    def _validate_markdown(self, content: str) -> tuple[bool, str]:
        """마크다운 구조 기본 검증."""
        if not content.strip():
            return False, "Empty content"
        # YAML frontmatter 쌍 확인
        if content.startswith("---"):
            second = content.find("\n---", 3)
            if second == -1:
                return False, "Unclosed YAML frontmatter"
        return True, "ok"

    def rollback(self, file_path: Path) -> tuple[bool, str]:
        """가장 최근 스냅샷으로 롤백."""
        snaps = sorted(self._snap_dir.glob(f"{file_path.stem}_*.md"))
        if not snaps:
            return False, "No snapshot available"
        latest = snaps[-1]
        try:
            file_path.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")
            _audit.log({"event": "rollback", "path": str(file_path), "from": str(latest)})
            return True, str(latest)
        except Exception as e:
            return False, str(e)

    def list_snapshots(self, file_path: Path) -> list[str]:
        """스냅샷 목록 반환."""
        return [str(s) for s in sorted(self._snap_dir.glob(f"{file_path.stem}_*.md"))]


# ══════════════════════════════════════════════════════════════════════════════
# Singleton Access
# ══════════════════════════════════════════════════════════════════════════════

_gate: Optional[SecurityGate] = None

def get_security_gate() -> SecurityGate:
    global _gate
    if _gate is None:
        _gate = SecurityGate()
    return _gate


def get_audit_trail() -> AuditTrail:
    return _audit


# worker.py / infra_dashboard.py 호환 별칭
def get_security_layer() -> SecurityGate:
    """get_security_gate() 별칭 — v4.0 API 통일."""
    return get_security_gate()


# SecurityGate.validate_input 편의 메서드 패치
def _validate_input(self, content: str, source: str = "unknown") -> "ValidationResult":
    """validate() 의 source-first 별칭."""
    return self.validate(content, source)

if not hasattr(SecurityGate, "validate_input"):
    SecurityGate.validate_input = _validate_input
