"""User-facing workflow contracts shared by the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InputDraft:
    input_type: str
    title: str = ""
    file_path: str = ""
    raw_text: str = ""


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    message: str
    field: str = ""


_TITLE_LABELS = {
    "paper": "논문 제목",
    "transcript": "스크립트 제목",
    "lecture": "강의 제목",
    "meeting": "회의 제목",
    "seminar": "세미나 제목",
    "podcast": "팟캐스트 제목",
    "dataset": "데이터셋 이름",
    "notes": "노트 제목",
}


def validate_input_draft(draft: InputDraft) -> ReadinessResult:
    """Return the first actionable item needed before analysis can start."""
    input_type = (draft.input_type or "notes").strip().lower()
    title = draft.title.strip()
    has_content = bool(draft.file_path.strip() or draft.raw_text.strip())

    title_label = _TITLE_LABELS.get(input_type)
    if title_label and not title:
        return ReadinessResult(False, f"{title_label}을 입력하세요.", "title")

    if not has_content:
        return ReadinessResult(False, "분석할 파일을 선택하거나 텍스트를 입력하세요.", "content")

    return ReadinessResult(True, "분석 준비 완료")
