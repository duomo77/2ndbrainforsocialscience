"""
contracts.py  —  ROS v7.0 Contract-Driven Interface Layer
==========================================================
철학: 모든 모듈 경계는 명시적 계약으로 정의된다.
      암묵적 딕셔너리 반환, 글로벌 상태, 숨겨진 의존성은 금지.

원칙:
  - Protocol 기반 구조적 타이핑 (duck typing 대신)
  - dataclass 기반 불변 데이터 전송 객체 (DTO)
  - 명시적 Result 타입 (예외 대신 오류 값)
  - 소유권 명확화 (어떤 모듈이 어떤 상태를 소유하는가)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Optional, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
E = TypeVar("E")


# ══════════════════════════════════════════════════════════════════════════════
# RESULT TYPE — 예외 없는 오류 처리
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: bool = True

    def unwrap(self) -> T:
        return self.value

    def map(self, fn) -> "Ok":
        return Ok(fn(self.value))


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    ok: bool = False
    context: str = ""

    def unwrap(self):
        raise RuntimeError(f"Unwrap called on Err: {self.error} | {self.context}")

    def map(self, fn) -> "Err":
        return self


Result = Ok | Err


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class InputType(str, Enum):
    PAPER       = "paper"
    TRANSCRIPT  = "transcript"
    DATASET     = "dataset"
    EQUATION    = "equation"
    NOTES       = "notes"
    QUALITATIVE = "qualitative"


class AnalysisStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    CACHED     = "cached"


class SaveStatus(str, Enum):
    SAVED    = "saved"
    UPDATED  = "updated"
    SKIPPED  = "skipped"
    FAILED   = "failed"


# ══════════════════════════════════════════════════════════════════════════════
# DATA TRANSFER OBJECTS (DTO) — 불변 도메인 객체
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AnalysisRequest:
    """분석 요청 DTO — worker.py 입력 계약."""
    input_type:    InputType
    content:       str
    title:         str         = ""
    authors:       str         = ""
    year:          str         = ""
    journal:       str         = ""
    zotero:        str         = ""
    discipline:    str         = "General"
    epistemic_mode: str        = "auto"
    context:       str         = ""
    source_name:   str         = ""
    material_type: str         = ""
    framework:     str         = ""
    dataset_name:  str         = ""
    file_info:     str         = ""
    date:          str         = ""
    extra:         dict        = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisResult:
    """분석 결과 DTO — worker.py 출력 계약."""
    status:        AnalysisStatus
    markdown:      str
    title:         str
    discipline:    str
    epistemic_mode: str
    topic:         str         = "Uncategorized"
    tokens_used:   int         = 0
    cached:        bool        = False
    engine_outputs: dict       = field(default_factory=dict)
    error:         str         = ""


@dataclass(frozen=True)
class SaveRequest:
    """Obsidian 저장 요청 DTO."""
    markdown:   str
    title:      str
    topic:      str
    discipline: str
    vault_path: str
    overwrite:  bool = True


@dataclass(frozen=True)
class SaveResult:
    """Obsidian 저장 결과 DTO."""
    status:    SaveStatus
    file_path: str
    topic:     str
    error:     str = ""


@dataclass(frozen=True)
class LLMConfig:
    """LLM 연결 설정 DTO."""
    api_key:  str
    base_url: str
    model:    str
    provider: str = ""

    def is_valid(self) -> bool:
        return bool(self.api_key and self.model)


@dataclass(frozen=True)
class VaultConfig:
    """Obsidian 볼트 설정 DTO."""
    vault_path:         str
    use_topic_folders:  bool = True
    auto_save:          bool = True
    create_index:       bool = True


@dataclass(frozen=True)
class ResearcherProfile:
    """연구자 프로파일 DTO."""
    name:        str   = ""
    discipline:  str   = ""
    interests:   tuple = ()
    methods:     tuple = ()
    projects:    tuple = ()
    questions:   tuple = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name, "discipline": self.discipline,
            "interests": list(self.interests), "methods": list(self.methods),
            "projects": list(self.projects), "questions": list(self.questions),
        }


# ══════════════════════════════════════════════════════════════════════════════
# PROTOCOLS — 모듈 경계 계약
# ══════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class AnalyzerProtocol(Protocol):
    """분석 엔진 계약."""
    def analyze(
        self,
        request: AnalysisRequest,
        llm_config: LLMConfig,
        profile: ResearcherProfile,
        existing_nodes: list[str],
        callback=None,
    ) -> Result: ...


@runtime_checkable
class StorageProtocol(Protocol):
    """저장 엔진 계약."""
    def save(self, request: SaveRequest) -> Result: ...
    def list_notes(self, vault_path: str) -> list[str]: ...
    def scan_nodes(self, vault_path: str) -> list[str]: ...


@runtime_checkable
class ClassifierProtocol(Protocol):
    """분류 엔진 계약."""
    def classify(self, title: str, journal: str, content: str) -> str: ...
    def get_all_topics(self) -> list[str]: ...


@runtime_checkable
class CacheProtocol(Protocol):
    """캐시 엔진 계약."""
    def get(self, key: str) -> Optional[str]: ...
    def set(self, key: str, value: str) -> None: ...
    def invalidate(self, key: str) -> None: ...


@runtime_checkable
class ObservabilityProtocol(Protocol):
    """관측성 엔진 계약."""
    def log_analysis(self, request: AnalysisRequest, result: AnalysisResult) -> None: ...
    def log_save(self, request: SaveRequest, result: SaveResult) -> None: ...
    def get_metrics(self) -> dict: ...


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def validate_analysis_request(req: AnalysisRequest) -> Result:
    """분석 요청 유효성 검사."""
    if not req.content or len(req.content.strip()) < 10:
        return Err("content_too_short", "Content must be at least 10 characters")
    if req.input_type == InputType.PAPER and not req.title:
        return Err("missing_title", "Paper analysis requires a title")
    if req.input_type == InputType.DATASET and not req.dataset_name:
        return Err("missing_dataset_name", "Dataset analysis requires a dataset name")
    return Ok(req)


def validate_llm_config(cfg: LLMConfig) -> Result:
    """LLM 설정 유효성 검사."""
    if not cfg.api_key:
        return Err("missing_api_key", "API key is required")
    if not cfg.model:
        return Err("missing_model", "Model name is required")
    return Ok(cfg)


def validate_save_request(req: SaveRequest) -> Result:
    """저장 요청 유효성 검사."""
    if not req.vault_path:
        return Err("missing_vault_path", "Vault path is required")
    if not req.markdown:
        return Err("empty_markdown", "Cannot save empty markdown")
    if not req.title:
        return Err("missing_title", "Note title is required")
    return Ok(req)
