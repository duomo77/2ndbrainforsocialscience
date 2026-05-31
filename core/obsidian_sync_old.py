"""
obsidian_sync.py - Obsidian 볼트 자동 동기화 모듈
주제별 서브폴더 저장, 인덱스 생성, 개념 스캔 기능 포함
"""

import os
import re
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional


def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip(". ")
    return name[:200]


def extract_frontmatter(markdown: str) -> tuple[dict, str]:
    """Markdown에서 YAML Frontmatter 파싱."""
    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    match = pattern.match(markdown)
    if match:
        try:
            fm = yaml.safe_load(match.group(1))
            return fm or {}, markdown[match.end():]
        except yaml.YAMLError:
            return {}, markdown
    return {}, markdown


def extract_wikilinks(markdown: str) -> list[str]:
    """Markdown에서 [[WikiLink]] 패턴 추출."""
    pattern = re.compile(r"\[\[([^\[\]|#]+?)(?:\|[^\[\]]+?)?\]\]")
    return list(set(pattern.findall(markdown)))


def _build_note_filename(fm: dict) -> str:
    """frontmatter에서 파일명 생성."""
    title = fm.get("title", "Untitled")
    year = fm.get("year", "")
    authors = fm.get("authors", [])
    first_author = (
        str(authors[0]).split()[-1]
        if isinstance(authors, list) and authors
        else ""
    )
    if first_author:
        return sanitize_filename(f"{first_author} ({year}) - {title}")
    return sanitize_filename(f"({year}) {title}" if year else title)


def resolve_save_path(
    vault_path: str,
    subfolder: str,
    topic: str,
    use_topic_folders: bool,
) -> Path:
    """
    저장 경로를 결정합니다.

    주제 폴더 사용 시:  vault/Papers/Econometrics/
    미사용 시:          vault/Papers/
    """
    base = Path(vault_path) / subfolder if subfolder else Path(vault_path)
    if use_topic_folders and topic and topic != "":
        return base / topic
    return base


def save_note_to_vault(
    vault_path: str,
    subfolder: str,
    markdown_content: str,
    topic: str = "Uncategorized",
    use_topic_folders: bool = True,
    custom_filename: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Obsidian 볼트에 노트를 저장합니다.

    Args:
        vault_path: 볼트 루트 경로
        subfolder: 볼트 내 기본 폴더 (예: "Papers")
        markdown_content: 저장할 Markdown 내용
        topic: 주제 폴더명 (예: "Econometrics")
        use_topic_folders: 주제별 서브폴더 사용 여부
        custom_filename: 사용자 지정 파일명

    Returns:
        (성공 여부, 저장 경로 또는 오류 메시지)
    """
    vault = Path(vault_path)
    if not vault.exists():
        return False, f"볼트 경로가 존재하지 않습니다: {vault_path}"

    target_dir = resolve_save_path(vault_path, subfolder, topic, use_topic_folders)
    target_dir.mkdir(parents=True, exist_ok=True)

    # 파일명 결정
    if custom_filename:
        filename = sanitize_filename(custom_filename)
    else:
        fm, _ = extract_frontmatter(markdown_content)
        filename = _build_note_filename(fm)

    if not filename.endswith(".md"):
        filename += ".md"

    file_path = target_dir / filename

    # 기존 파일 백업 후 덮어쓰기
    if file_path.exists():
        backup = file_path.with_suffix(
            f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        file_path.rename(backup)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return True, str(file_path)


def create_index_note(
    vault_path: str,
    subfolder: str,
    notes_metadata: list[dict],
    use_topic_folders: bool = True,
) -> tuple[bool, str]:
    """
    Papers 폴더의 _INDEX.md (Map of Content) 생성/업데이트.
    주제 폴더 사용 시 주제별 섹션으로 구성.
    """
    from core.classifier import TOPIC_META

    vault = Path(vault_path)
    base_dir = vault / subfolder if subfolder else vault
    base_dir.mkdir(parents=True, exist_ok=True)
    index_path = base_dir / "_INDEX.md"

    lines = [
        "---",
        "title: Papers Index (MOC)",
        f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "tags: [index, MOC, causal-inference]",
        "---",
        "",
        "# 📚 Papers Index — Map of Content",
        "",
        f"> **총 {len(notes_metadata)}편** 등록 | "
        f"마지막 업데이트: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        "",
    ]

    if use_topic_folders:
        # 주제별 그룹화
        groups: dict[str, list] = {}
        for meta in notes_metadata:
            topic = meta.get("identification", meta.get("topic", "Uncategorized"))
            # frontmatter의 identification을 주제 폴더로 매핑
            folder = _identification_to_folder(topic)
            groups.setdefault(folder, []).append(meta)

        # 주제 순서 (TOPIC_META 순서 따름)
        for folder in list(TOPIC_META.keys()) + ["Uncategorized"]:
            papers = groups.get(folder, [])
            if not papers:
                continue
            meta_info = TOPIC_META.get(folder, {"icon": "📂", "label": folder})
            lines.append(
                f"## {meta_info['icon']} {folder}  "
                f"<small>({meta_info['label']})</small>"
            )
            lines.append("")
            for p in sorted(papers, key=lambda x: str(x.get("year", "0")), reverse=True):
                title = p.get("title", "Unknown")
                authors = p.get("authors", [])
                year = p.get("year", "")
                first_author = (
                    str(authors[0]).split()[-1]
                    if isinstance(authors, list) and authors else "Unknown"
                )
                fn = sanitize_filename(
                    f"{first_author} ({year}) - {title}"
                    if first_author != "Unknown" else f"({year}) {title}"
                )
                author_str = (
                    ", ".join(str(a) for a in authors[:2])
                    if isinstance(authors, list) else str(authors)
                )
                lines.append(
                    f"- [[{folder}/{fn}|{fn}]] "
                    f"— {author_str} ({year})"
                )
            lines.append("")
    else:
        # 평면 목록
        for p in sorted(notes_metadata, key=lambda x: str(x.get("year", "0")), reverse=True):
            title = p.get("title", "Unknown")
            authors = p.get("authors", [])
            year = p.get("year", "")
            first_author = (
                str(authors[0]).split()[-1]
                if isinstance(authors, list) and authors else "Unknown"
            )
            fn = sanitize_filename(
                f"{first_author} ({year}) - {title}"
                if first_author != "Unknown" else f"({year}) {title}"
            )
            author_str = (
                ", ".join(str(a) for a in authors[:2])
                if isinstance(authors, list) else str(authors)
            )
            lines.append(f"- [[{fn}]] — {author_str} ({year})")

    content = "\n".join(lines)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)

    return True, str(index_path)


def _identification_to_folder(identification: str) -> str:
    """
    frontmatter의 identification 값을 주제 폴더명으로 변환.
    예: "DML" → "Econometrics", "Causal Forest" → "Econometrics"
    """
    mapping = {
        "DML": "Econometrics",
        "Double Machine Learning": "Econometrics",
        "Causal Forest": "Econometrics",
        "IV": "Econometrics",
        "DID": "Econometrics",
        "RDD": "Econometrics",
        "Difference-in-Differences": "Econometrics",
        "Regression Discontinuity": "Econometrics",
        "Instrumental Variables": "Econometrics",
    }
    return mapping.get(identification, identification if identification else "Uncategorized")


def scan_vault_concepts(vault_path: str, subfolder: str) -> list[str]:
    """볼트 내 기존 노트에서 WikiLink 개념 목록 스캔."""
    vault = Path(vault_path)
    base = vault / subfolder if subfolder else vault

    if not base.exists():
        return []

    concepts = set()
    for md_file in base.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            concepts.update(extract_wikilinks(content))
            concepts.add(md_file.stem)
        except (IOError, UnicodeDecodeError):
            continue

    return sorted(concepts)


def get_vault_notes_metadata(
    vault_path: str,
    subfolder: str,
    use_topic_folders: bool = True,
) -> list[dict]:
    """볼트 내 모든 노트의 frontmatter 메타데이터 수집."""
    vault = Path(vault_path)
    base = vault / subfolder if subfolder else vault

    if not base.exists():
        return []

    metadata_list = []
    for md_file in base.rglob("*.md"):
        if md_file.name.startswith("_"):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            fm, _ = extract_frontmatter(content)
            if fm:
                fm["_filename"] = md_file.stem
                # 주제 폴더 정보 추가
                if use_topic_folders:
                    # 파일이 속한 서브폴더명 = 주제
                    rel = md_file.relative_to(base)
                    fm["_topic_folder"] = rel.parts[0] if len(rel.parts) > 1 else "Uncategorized"
                metadata_list.append(fm)
        except (IOError, UnicodeDecodeError):
            continue

    return metadata_list


def get_topic_folder_stats(vault_path: str, subfolder: str) -> dict[str, int]:
    """주제별 노트 수 통계 반환."""
    vault = Path(vault_path)
    base = vault / subfolder if subfolder else vault

    if not base.exists():
        return {}

    stats: dict[str, int] = {}
    for item in base.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            count = len(list(item.glob("*.md")))
            if count > 0:
                stats[item.name] = count

    # 루트 노트 (주제 폴더 없는 것)
    root_notes = len([f for f in base.glob("*.md") if not f.name.startswith("_")])
    if root_notes > 0:
        stats["(루트)"] = root_notes

    return stats
