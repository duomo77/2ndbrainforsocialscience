"""
parsers.py — Multi-Source Input Parser
=======================================
지원 입력: PDF, TXT/MD, CSV/Excel, 음성 스크립트(TXT), 코드 파일
"""

import os
import re
from pathlib import Path
from typing import Optional


# ── PDF Parser ────────────────────────────────────────────────────────────────
def parse_pdf(path: str, max_chars: int = 80000) -> tuple[str, dict]:
    """PDF에서 텍스트 추출. (text, metadata) 반환."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        meta = doc.metadata or {}
        pages = []
        for page in doc:
            pages.append(page.get_text())
        text = "\n".join(pages)
        doc.close()
        return text[:max_chars], {
            "title":   meta.get("title", ""),
            "author":  meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "pages":   len(pages),
        }
    except ImportError:
        return f"[PyMuPDF not installed — pip install PyMuPDF]", {}
    except Exception as e:
        return f"[PDF parse error: {e}]", {}


# ── Text / Markdown Parser ────────────────────────────────────────────────────
def parse_text(path: str, max_chars: int = 80000) -> str:
    """텍스트/마크다운 파일 읽기."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]
    except Exception as e:
        return f"[Text parse error: {e}]"


# ── CSV / Excel Dataset Parser ────────────────────────────────────────────────
def parse_dataset(path: str) -> tuple[str, dict]:
    """
    CSV/Excel 파일을 분석하여 구조 요약 반환.
    (summary_text, stats_dict) 반환.
    """
    try:
        import pandas as pd
        ext = Path(path).suffix.lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(path, nrows=5000)
        elif ext == ".tsv":
            df = pd.read_csv(path, nrows=5000, sep="\t", encoding="utf-8", encoding_errors="replace")
        else:
            df = pd.read_csv(path, nrows=5000, encoding="utf-8", encoding_errors="replace")

        n_rows, n_cols = df.shape
        dtypes = df.dtypes.astype(str).to_dict()
        missing = df.isnull().sum().to_dict()
        missing_pct = {k: round(v / n_rows * 100, 1) for k, v in missing.items() if v > 0}

        # 수치형 변수 요약
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        desc = df[numeric_cols].describe().to_string() if numeric_cols else "No numeric columns"

        # 범주형 변수
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        cat_summary = {}
        for c in cat_cols[:10]:
            cat_summary[c] = df[c].value_counts().head(5).to_dict()

        # 패널 구조 추론
        panel_hint = _infer_panel_structure(df)

        summary = f"""Dataset: {Path(path).name}
Shape: {n_rows:,} rows × {n_cols} columns
File: {path}

=== Column Types ===
{_format_dtypes(dtypes)}

=== Missing Data ===
{_format_missing(missing_pct) if missing_pct else 'No missing values detected'}

=== Numeric Summary ===
{desc}

=== Categorical Variables (top values) ===
{_format_cat(cat_summary)}

=== Panel Structure Inference ===
{panel_hint}

=== First 5 Rows ===
{df.head(5).to_string()}
"""
        stats = {
            "n_rows": n_rows, "n_cols": n_cols,
            "numeric_cols": numeric_cols,
            "cat_cols": cat_cols,
            "missing_pct": missing_pct,
            "panel_hint": panel_hint,
        }
        return summary[:50000], stats

    except ImportError:
        return "[pandas not installed — pip install pandas openpyxl]", {}
    except Exception as e:
        return f"[Dataset parse error: {e}]", {}


def _infer_panel_structure(df) -> str:
    """패널 구조 자동 추론."""
    cols_lower = {c.lower(): c for c in df.columns}
    hints = []

    # ID 변수 후보
    id_candidates = [c for c in cols_lower if any(k in c for k in
        ["id", "code", "fips", "iso", "country", "firm", "person", "individual", "unit"])]
    if id_candidates:
        hints.append(f"Possible ID vars: {id_candidates[:5]}")

    # 시간 변수 후보
    time_candidates = [c for c in cols_lower if any(k in c for k in
        ["year", "date", "time", "month", "quarter", "period", "wave"])]
    if time_candidates:
        hints.append(f"Possible time vars: {time_candidates[:5]}")

    if id_candidates and time_candidates:
        id_col   = cols_lower[id_candidates[0]]
        time_col = cols_lower[time_candidates[0]]
        n_units  = df[id_col].nunique()
        n_periods = df[time_col].nunique()
        hints.append(f"Likely panel: N={n_units:,} units × T={n_periods} periods")
        # 균형 패널 확인
        expected = n_units * n_periods
        actual   = len(df)
        balance  = "balanced" if abs(expected - actual) < expected * 0.05 else "unbalanced"
        hints.append(f"Panel balance: {balance} (expected {expected:,}, actual {actual:,})")

    # 처치 변수 후보
    binary_cols = [c for c in df.columns if df[c].dropna().isin([0, 1]).all() and df[c].nunique() == 2]
    if binary_cols:
        hints.append(f"Binary (treatment?) candidates: {binary_cols[:5]}")

    return "\n".join(hints) if hints else "Structure unclear — no obvious ID/time variables found"


def _format_dtypes(dtypes: dict) -> str:
    lines = []
    for col, dtype in list(dtypes.items())[:30]:
        lines.append(f"  {col}: {dtype}")
    if len(dtypes) > 30:
        lines.append(f"  ... (+{len(dtypes)-30} more)")
    return "\n".join(lines)

def _format_missing(missing_pct: dict) -> str:
    lines = []
    for col, pct in sorted(missing_pct.items(), key=lambda x: -x[1])[:20]:
        bar = "█" * int(pct / 5)
        lines.append(f"  {col}: {pct}% {bar}")
    return "\n".join(lines)

def _format_cat(cat_summary: dict) -> str:
    lines = []
    for col, vals in cat_summary.items():
        lines.append(f"  {col}: {dict(list(vals.items())[:3])}")
    return "\n".join(lines)


# ── Transcript / Script Parser ────────────────────────────────────────────────
def parse_transcript(path: str, max_chars: int = 80000, raw_text: str = "") -> tuple[str, dict]:
    """
    음성 스크립트/강의록 텍스트 파일 파싱.
    화자 분리, 타임스탬프 제거, 구조 추출.
    raw_text가 있으면 파일 읽기 없이 직접 처리.
    """
    try:
        if raw_text:
            text = raw_text
        elif path:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        else:
            return "", {}
        meta = _extract_transcript_meta(text)
        cleaned = _clean_transcript(text)
        return cleaned[:max_chars], meta
    except Exception as e:
        return f"[Transcript parse error: {e}]", {}


def _extract_transcript_meta(text: str) -> dict:
    """스크립트에서 메타데이터 추출."""
    meta = {"speakers": [], "duration": "", "word_count": len(text.split())}
    # 화자 패턴: "Speaker:", "SPEAKER:", "[Name]:", "Name:"
    speakers = re.findall(r'^([A-Z][A-Za-z\s]+):\s', text, re.MULTILINE)
    speakers += re.findall(r'\[([A-Z][A-Za-z\s]+)\]', text)
    meta["speakers"] = list(set(speakers))[:10]
    # 타임스탬프 패턴
    timestamps = re.findall(r'\d{1,2}:\d{2}(?::\d{2})?', text)
    if timestamps:
        meta["duration"] = timestamps[-1] if timestamps else ""
    return meta


def _clean_transcript(text: str) -> str:
    """타임스탬프 및 불필요한 마커 제거."""
    # [00:01:23] 형식 타임스탬프 제거
    text = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', '', text)
    # (00:01:23) 형식
    text = re.sub(r'\(\d{1,2}:\d{2}(?::\d{2})?\)', '', text)
    # 연속 공백 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def parse_audio(path: str) -> tuple[str, dict]:
    """
    Audio files need transcription before ROS text analysis.

    Most configured chat providers, including many China OpenAI-compatible
    endpoints, do not guarantee a Whisper-compatible audio endpoint. This keeps
    binary audio from being read as text and sent to the LLM.
    """
    name = Path(path).name
    return (
        f"[Audio transcription required: {name}]\n"
        "Please transcribe this audio file to .txt, .md, .srt, or .vtt before analysis.",
        {
            "file": name,
            "requires_transcription": True,
            "supported_transcript_formats": [".txt", ".md", ".srt", ".vtt"],
        },
    )


# ── Auto-detect Input Type ────────────────────────────────────────────────────
def detect_input_type(path: str) -> str:
    """파일 확장자로 입력 유형 자동 감지."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":                          return "paper"
    if ext in (".csv", ".tsv", ".xlsx", ".xls"): return "dataset"
    if ext in (".srt", ".vtt"):                return "transcript"
    if ext in (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".webm"):
        return "audio"
    if ext in (".txt", ".md", ".rst"):
        # 내용 기반 추론
        try:
            sample = Path(path).read_text(encoding="utf-8", errors="replace")[:2000]
            if _looks_like_transcript(sample):  return "transcript"
            if _looks_like_paper(sample):       return "paper"
        except Exception:
            pass
        return "notes"
    if ext in (".py", ".r", ".do", ".jl"):     return "code"
    if ext in (".tex",):                        return "paper"
    return "notes"


def _looks_like_transcript(text: str) -> bool:
    """텍스트가 강의/음성 스크립트처럼 보이는지 확인."""
    patterns = [
        r'\d{1,2}:\d{2}',          # 타임스탬프
        r'^[A-Z][A-Za-z]+:\s',     # 화자: 발화
        r'\[inaudible\]',
        r'\[laughter\]',
        r'um\b|uh\b|yeah\b',
    ]
    matches = sum(1 for p in patterns if re.search(p, text, re.MULTILINE | re.IGNORECASE))
    return matches >= 2


def _looks_like_paper(text: str) -> bool:
    """텍스트가 학술 논문처럼 보이는지 확인."""
    keywords = ["abstract", "introduction", "methodology", "conclusion",
                "references", "journal", "doi", "p-value", "regression"]
    text_lower = text.lower()
    matches = sum(1 for k in keywords if k in text_lower)
    return matches >= 3


# ── Code Parser ───────────────────────────────────────────────────────────────
def parse_code(path: str) -> tuple[str, dict]:
    """코드 파일 파싱 및 구조 요약."""
    try:
        code = Path(path).read_text(encoding="utf-8", errors="replace")
        ext  = Path(path).suffix.lower()
        meta = {
            "language": {"py": "Python", "r": "R", "do": "Stata",
                         "jl": "Julia", "m": "MATLAB"}.get(ext.lstrip("."), "Unknown"),
            "lines": len(code.split("\n")),
        }
        return code[:40000], meta
    except Exception as e:
        return f"[Code parse error: {e}]", {}
