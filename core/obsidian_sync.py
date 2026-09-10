"""
obsidian_sync.py — Obsidian Vault Sync Engine (ROS Edition)
============================================================
- 입력 유형별 폴더 자동 분류 (Papers/Transcripts/Datasets/...)
- 논문은 주제별 서브폴더 (Papers/Econometrics/, Papers/Finance/, ...)
- _INDEX.md (MOC) 자동 갱신
- Obsidian URI 연동
"""

import os
import re
import tempfile
import time
from pathlib import Path
from datetime import datetime

import yaml

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# wikilink parsing unified in core.utils.markdown_utils (audit F-16)
_concept_cache: dict[str, tuple[int, int, tuple[str, ...]]] = {}
_notes_cache: dict[str, tuple[float, list[dict]]] = {}
_NOTES_CACHE_TTL_SECONDS = 5.0


FOLDER_MAP = {
    "paper":      "Papers",
    "transcript": "Transcripts",
    "dataset":    "Datasets",
    "notes":      "Notes",
    "equation":   "Equations",
    "code":       "Code",
    "concept":    "Concepts",
    "research_context": "Contexts",
    "research_intelligence": "Research Intelligence",
    "methodology_atlas": "Methodology Atlas",
}

JOURNAL_TOPIC_MAP = {
    "econometrica":                    "Econometrics",
    "journal of econometrics":         "Econometrics",
    "review of economic studies":      "Econometrics",
    "review of economics and statistics": "Econometrics",
    "american economic review":        "GeneralEconomics",
    "quarterly journal of economics":  "GeneralEconomics",
    "journal of political economy":    "GeneralEconomics",
    "journal of labor economics":      "LaborEconomics",
    "industrial and labor relations":  "LaborEconomics",
    "journal of finance":              "Finance",
    "journal of financial economics":  "Finance",
    "review of financial studies":     "Finance",
    "journal of health economics":     "HealthEconomics",
    "journal of public economics":     "PublicEconomics",
    "journal of development economics":"DevelopmentEconomics",
    "rand journal":                    "IndustrialOrganization",
    "journal of machine learning":     "MachineLearning",
    "annals of statistics":            "Statistics",
    "nber":                            "WorkingPapers",
    "ssrn":                            "WorkingPapers",
    "arxiv":                           "WorkingPapers",
}

TOPIC_ICONS = {
    "Econometrics":           "📐",
    "MachineLearning":        "🤖",
    "GeneralEconomics":       "📊",
    "LaborEconomics":         "👷",
    "Finance":                "💹",
    "HealthEconomics":        "🏥",
    "PublicEconomics":        "🏛",
    "DevelopmentEconomics":   "🌍",
    "IndustrialOrganization": "🏭",
    "Statistics":             "📈",
    "WorkingPapers":          "📝",
    "Transcripts":            "🎙",
    "Datasets":               "🗃",
    "Notes":                  "📋",
    "Equations":              "∑",
    "Code":                   "💻",
    "Concepts":               "💡",
    "Uncategorized":          "📂",
}


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:120]


def _safe_path_component(value: str, label: str) -> str:
    """Validate user-controlled folder names as one filesystem component."""
    value = str(value or "").strip()
    if (
        not value
        or value in {".", ".."}
        or Path(value).name != value
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError(f"Invalid {label}")
    safe = sanitize_filename(value)
    if not safe or safe in {".", ".."}:
        raise ValueError(f"Invalid {label}")
    return safe


def _within_vault(candidate: Path, vault: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(vault)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _atomic_write_text(path: Path, content: str) -> None:
    """Durably replace a UTF-8 text file without exposing a partial write."""
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        if hasattr(os, "O_DIRECTORY"):
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temp_path.unlink(missing_ok=True)


def detect_topic(content: str, journal: str = "") -> str:
    jl = journal.lower()
    for key, topic in JOURNAL_TOPIC_MAP.items():
        if key in jl:
            return topic
    cl = content.lower()
    if any(k in cl for k in ["machine learning", "random forest", "neural network", "xgboost", "deep learning"]):
        return "MachineLearning"
    if any(k in cl for k in ["labor", "wage", "employment", "worker", "union"]):
        return "LaborEconomics"
    if any(k in cl for k in ["health", "mortality", "hospital", "insurance", "medicaid"]):
        return "HealthEconomics"
    if any(k in cl for k in ["tax", "public good", "fiscal", "government spending", "welfare"]):
        return "PublicEconomics"
    if any(k in cl for k in ["development", "poverty", "aid", "microfinance", "gdp per capita"]):
        return "DevelopmentEconomics"
    if any(k in cl for k in ["stock", "asset pricing", "portfolio", "return", "volatility"]):
        return "Finance"
    if any(k in cl for k in ["market structure", "oligopoly", "entry", "antitrust", "merger"]):
        return "IndustrialOrganization"
    if any(k in cl for k in ["econometric", "causal", "identification", "estimator", "panel data"]):
        return "Econometrics"
    return "Uncategorized"


def extract_frontmatter(markdown: str) -> dict:
    try:
        match = _FRONTMATTER_PATTERN.match(markdown)
        if match:
            return yaml.safe_load(match.group(1)) or {}
    except Exception:
        pass
    return {}


def extract_wikilinks(markdown: str) -> list:
    from core.utils.markdown_utils import extract_wikilink_targets
    return list(set(extract_wikilink_targets(markdown)))


def save_note_to_vault(
    vault_path: str,
    markdown_content: str,
    title: str = "",
    input_type: str = "paper",
    journal: str = "",
    topic_override: str = "",
    custom_filename: str = "",
    update_index: bool = True,
) -> tuple:
    """
    Obsidian 볼트에 노트 저장.
    Returns: (success: bool, path_or_error: str, topic: str)
    """
    vault_input = Path(vault_path).expanduser()
    if not vault_input.exists() or not vault_input.is_dir():
        return False, f"볼트 경로 없음: {vault_path}", ""
    try:
        vault = vault_input.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return False, f"볼트 경로 확인 실패: {exc}", ""

    base_folder = FOLDER_MAP.get(input_type, "Notes")

    if input_type == "paper":
        try:
            topic = (
                _safe_path_component(topic_override, "topic override")
                if topic_override
                else detect_topic(markdown_content, journal)
            )
        except ValueError as exc:
            return False, str(exc), ""
        folder = vault / base_folder / topic
    else:
        topic = base_folder
        folder = vault / base_folder

    if not _within_vault(folder, vault):
        return False, "저장 경로가 볼트 범위를 벗어납니다.", ""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        folder = folder.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return False, f"저장 폴더 생성 실패: {exc}", ""
    if not _within_vault(folder, vault):
        return False, "저장 폴더가 볼트 범위를 벗어납니다.", ""

    # 파일명 결정
    if custom_filename:
        safe_name = sanitize_filename(custom_filename)
    elif title:
        safe_name = sanitize_filename(title)
    else:
        fm = extract_frontmatter(markdown_content)
        safe_name = sanitize_filename(fm.get("title", "Untitled"))

    if not safe_name.endswith(".md"):
        safe_name += ".md"

    filepath = folder / safe_name
    if not _within_vault(filepath, vault):
        return False, "노트 경로가 볼트 범위를 벗어납니다.", ""
    if filepath.is_symlink():
        return False, "심볼릭 링크 대상에는 노트를 저장할 수 없습니다.", ""

    # Existing content stays in place until the final atomic replacement.
    try:
        if filepath.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = vault / ".ros_backups"
            if not _within_vault(backup_dir, vault):
                return False, "백업 경로가 볼트 범위를 벗어납니다.", ""
            backup_dir.mkdir(exist_ok=True)
            backup_dir = backup_dir.resolve(strict=True)
            if not _within_vault(backup_dir, vault):
                return False, "백업 폴더가 볼트 범위를 벗어납니다.", ""
            bak = backup_dir / f"{filepath.stem}.bak_{ts}.md"
            _atomic_write_text(bak, filepath.read_text(encoding="utf-8"))
            _evict_old_backups(backup_dir, filepath.stem, keep=5)
        _atomic_write_text(filepath, markdown_content)
    except (OSError, UnicodeError) as exc:
        return False, f"원자적 노트 저장 실패: {exc}", ""

    if update_index:
        _update_index(vault, title or filepath.stem, str(filepath), input_type, topic)

    _invalidate_vault_caches(vault)
    return True, str(filepath), topic


def _invalidate_vault_caches(vault: Path):
    prefix = str(vault.resolve())
    for key in list(_concept_cache):
        if key.startswith(prefix):
            _concept_cache.pop(key, None)
    _notes_cache.pop(prefix, None)


def _evict_old_backups(backup_dir: Path, stem: str, keep: int = 5):
    """B-09: 노트당 백업을 `keep`개로 제한, 가장 오래된 것부터 삭제."""
    try:
        backups = sorted(backup_dir.glob(f"{stem}.bak_*.md"))
        while len(backups) > keep:
            backups[0].unlink(missing_ok=True)
            backups = backups[1:]
    except OSError:
        pass


def _is_scannable_note(md: Path, base: Path) -> bool:
    """B-09/F-14: 백업·숨김 경로는 개념/노트 스캔에서 제외한다."""
    if ".bak_" in md.name or md.name.startswith("_"):
        return False
    try:
        rel_parts = md.relative_to(base).parts
    except ValueError:
        rel_parts = md.parts
    return not any(part.startswith(".") for part in rel_parts[:-1])


def _update_index(vault: Path, title: str, note_path: str, input_type: str, topic: str):
    index_path = vault / "_INDEX.md"
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        rel = os.path.relpath(note_path, str(vault)).replace("\\", "/")
    except ValueError:
        rel = note_path
    icon = TOPIC_ICONS.get(topic, "📄")
    entry = f"- {icon} [[{title}]] — `{rel}` *(added {today})*\n"

    if not index_path.exists():
        _create_index(vault)

    content = index_path.read_text(encoding="utf-8")
    header = f"## {icon} {topic}"
    # C-03: 중복 등록 방지 — 동일 노트 엔트리가 이미 있으면 그 자리에서 갱신.
    # (재분석마다 _INDEX.md가 부풀던 문제를 차단)
    link_marker = f"[[{title}]]"
    if header in content:
        idx = content.index(header) + len(header)
        nxt = content.find("\n## ", idx)
        section_end = nxt if nxt != -1 else len(content)
        section_lines = content[idx:section_end].splitlines(keepends=True)
        new_lines = []
        replaced = False
        for line in section_lines:
            if link_marker in line and not replaced:
                new_lines.append(entry)
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.insert(0, entry)
        content = content[:idx] + "".join(new_lines) + content[section_end:]
    else:
        content += f"\n{header}\n{entry}"
    _atomic_write_text(index_path, content)


def _create_index(vault: Path):
    lines = [
        "---",
        "title: ROS Knowledge Index",
        f"updated: {datetime.now().isoformat()}",
        "type: index",
        "---",
        "",
        "# 🧠 Research Operating System — Knowledge Index",
        "",
        "> *Atomic knowledge primitives · Karpathy-style*",
        "",
    ]
    for topic, icon in TOPIC_ICONS.items():
        lines.append(f"## {icon} {topic}")
        lines.append("")
    _atomic_write_text(vault / "_INDEX.md", "\n".join(lines))


def scan_vault_concepts(vault_path: str, subfolder: str = "") -> list:
    base = Path(vault_path) / subfolder if subfolder else Path(vault_path)
    if not base.exists():
        return []
    concepts = set()
    for md in base.rglob("*.md"):
        if not _is_scannable_note(md, base):
            continue
        try:
            st = md.stat()
            cache_key = str(md.resolve())
            fingerprint = (st.st_mtime_ns, st.st_size)
            cached = _concept_cache.get(cache_key)
            if cached and cached[:2] == fingerprint:
                file_concepts = cached[2]
            else:
                text = md.read_text(encoding="utf-8", errors="replace")
                file_concepts = tuple(sorted(set(extract_wikilinks(text) + [md.stem])))
                _concept_cache[cache_key] = (*fingerprint, file_concepts)
            concepts.update(file_concepts)
        except Exception:
            pass
    return sorted(concepts)


def list_notes(vault_path: str) -> list:
    if not vault_path:
        return []
    vault = Path(vault_path)
    cache_key = str(vault.absolute())
    now = time.time()
    cached = _notes_cache.get(cache_key)
    if cached and now - cached[0] <= _NOTES_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]
    notes = []
    for md in vault.rglob("*.md"):
        if not _is_scannable_note(md, vault):
            continue
        try:
            st = md.stat()
            notes.append({
                "title":    md.stem,
                "path":     str(md),
                "folder":   md.parent.name,
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size":     st.st_size,
            })
        except Exception:
            pass
    result = sorted(notes, key=lambda x: x["modified"], reverse=True)
    _notes_cache[cache_key] = (now, [dict(item) for item in result])
    return result


def get_vault_stats(vault_path: str) -> dict:
    notes = list_notes(vault_path)
    by_folder = {}
    for n in notes:
        f = n["folder"]
        by_folder[f] = by_folder.get(f, 0) + 1
    return {"total_notes": len(notes), "by_folder": by_folder}


def open_in_obsidian(vault_path: str, note_path: str):
    import subprocess
    import urllib.parse
    import sys
    vault_name = Path(vault_path).name
    try:
        rel = os.path.relpath(note_path, vault_path).replace("\\", "/")
    except ValueError:
        rel = note_path
    uri = f"obsidian://open?vault={urllib.parse.quote(vault_name)}&file={urllib.parse.quote(rel)}"
    try:
        if sys.platform == "win32":
            os.startfile(uri)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", uri])
        else:
            subprocess.Popen(["xdg-open", uri])
    except Exception:
        pass
