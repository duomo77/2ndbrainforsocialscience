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
import time
from pathlib import Path
from datetime import datetime

import yaml

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_PATTERN = re.compile(r'\[\[([^\]\|#]+?)(?:\|[^\]]+?)?\]\]')
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
    return list(set(_WIKILINK_PATTERN.findall(markdown)))


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
    vault = Path(vault_path)
    if not vault.exists():
        return False, f"볼트 경로 없음: {vault_path}", ""

    base_folder = FOLDER_MAP.get(input_type, "Notes")

    if input_type == "paper":
        topic = topic_override or detect_topic(markdown_content, journal)
        folder = vault / base_folder / topic
    else:
        topic = base_folder
        folder = vault / base_folder

    folder.mkdir(parents=True, exist_ok=True)

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

    # 원자적 쓰기: tmp 파일에 먼저 쓴 후 rename (v4.0)
    tmp_path = filepath.with_suffix(".tmp")
    try:
        tmp_path.write_text(markdown_content, encoding="utf-8")
        # 기존 파일 백업 후 원자적 교체
        if filepath.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = folder / f"{filepath.stem}.bak_{ts}.md"
            filepath.rename(bak)
        tmp_path.replace(filepath)
    except Exception:
        # 원자적 쓰기 실패 시 직접 쓰기 폴백
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        filepath.write_text(markdown_content, encoding="utf-8")

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
    if header in content:
        idx = content.index(header) + len(header)
        nxt = content.find("\n## ", idx)
        content = content[:nxt] + entry + content[nxt:] if nxt != -1 else content + entry
    else:
        content += f"\n{header}\n{entry}"
    index_path.write_text(content, encoding="utf-8")


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
    (vault / "_INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def scan_vault_concepts(vault_path: str, subfolder: str = "") -> list:
    base = Path(vault_path) / subfolder if subfolder else Path(vault_path)
    if not base.exists():
        return []
    concepts = set()
    for md in base.rglob("*.md"):
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
        if md.name.startswith("_"):
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
