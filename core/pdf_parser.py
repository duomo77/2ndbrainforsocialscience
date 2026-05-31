"""
pdf_parser.py - PDF 텍스트 추출 모듈
PyMuPDF(fitz)를 사용하여 논문 PDF에서 텍스트를 추출
"""

import fitz  # PyMuPDF
from pathlib import Path


def extract_text_from_pdf(pdf_path: str, max_chars: int = 80000) -> str:
    """
    PDF 파일에서 텍스트를 추출합니다.

    Args:
        pdf_path: PDF 파일 경로
        max_chars: 최대 추출 문자 수 (LLM 컨텍스트 제한 대응)

    Returns:
        추출된 텍스트 문자열
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("PDF 파일만 지원합니다.")

    doc = fitz.open(str(path))
    pages_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages_text.append(f"[Page {page_num + 1}]\n{text}")

    doc.close()

    full_text = "\n\n".join(pages_text)

    # 컨텍스트 제한 처리: 앞부분(서론/방법론) + 뒷부분(결과) 우선 보존
    if len(full_text) > max_chars:
        half = max_chars // 2
        full_text = (
            full_text[:half]
            + "\n\n... [중간 내용 생략 - 컨텍스트 제한] ...\n\n"
            + full_text[-half:]
        )

    return full_text


def get_pdf_metadata(pdf_path: str) -> dict:
    """PDF 메타데이터(제목, 저자 등) 추출."""
    doc = fitz.open(pdf_path)
    meta = doc.metadata
    doc.close()
    return {
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "subject": meta.get("subject", ""),
        "keywords": meta.get("keywords", ""),
        "creation_date": meta.get("creationDate", ""),
    }
