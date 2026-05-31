"""
memory.py — Long-Term Research Memory & Researcher Profile
===========================================================
연구자의 관심사, 방법론 선호도, 반복 개념, 미해결 질문,
활성 논문 초안을 영속적으로 관리합니다.
"""

import json
import os
from datetime import datetime
from pathlib import Path


MEMORY_DIR = Path.home() / ".ros_memory"
PROFILE_FILE   = MEMORY_DIR / "researcher_profile.json"
CONCEPTS_FILE  = MEMORY_DIR / "concept_registry.json"
QUESTIONS_FILE = MEMORY_DIR / "open_questions.json"
GRAPH_FILE     = MEMORY_DIR / "knowledge_graph.json"


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


# ── Researcher Profile ─────────────────────────────────────────────────────────
DEFAULT_PROFILE = {
    "name": "",
    "institution": "",
    "field": "Economics",
    "subfield": "",
    "methods": [],
    "interests": "",
    "active_qs": "",
    "preferred_estimators": [],
    "preferred_software": [],
    "notes": "",
    "updated": "",
}

def load_profile() -> dict:
    _ensure_dir()
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_PROFILE.copy()

def save_profile(profile: dict):
    _ensure_dir()
    profile["updated"] = datetime.now().isoformat()
    PROFILE_FILE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Concept Registry (Knowledge Graph Nodes) ──────────────────────────────────
def load_concepts() -> dict:
    """개념 레지스트리 로드: {concept_name: {type, description, count, last_seen}}"""
    _ensure_dir()
    if CONCEPTS_FILE.exists():
        try:
            return json.loads(CONCEPTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_concepts(concepts: dict):
    _ensure_dir()
    CONCEPTS_FILE.write_text(json.dumps(concepts, ensure_ascii=False, indent=2), encoding="utf-8")

def register_concepts(new_concepts: list, concept_type: str = "general"):
    """새 개념들을 레지스트리에 등록/업데이트."""
    concepts = load_concepts()
    today = datetime.now().isoformat()
    for c in new_concepts:
        c = c.strip()
        if not c: continue
        if c in concepts:
            concepts[c]["count"] = concepts[c].get("count", 0) + 1
            concepts[c]["last_seen"] = today
        else:
            concepts[c] = {
                "type": concept_type,
                "description": "",
                "count": 1,
                "first_seen": today,
                "last_seen": today,
            }
    save_concepts(concepts)

def get_concept_list() -> list:
    """위키링크 생성용 개념 이름 목록 반환."""
    return sorted(load_concepts().keys())


# ── Open Research Questions ────────────────────────────────────────────────────
def load_questions() -> list:
    _ensure_dir()
    if QUESTIONS_FILE.exists():
        try:
            return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def save_questions(questions: list):
    _ensure_dir()
    QUESTIONS_FILE.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")

def add_question(question: str, source: str = ""):
    questions = load_questions()
    questions.append({
        "question": question,
        "source": source,
        "status": "open",
        "added": datetime.now().isoformat(),
    })
    save_questions(questions)


# ── Knowledge Graph ────────────────────────────────────────────────────────────
def load_graph() -> dict:
    """지식 그래프 로드: {node: {edges: [], type, note_path}}"""
    _ensure_dir()
    if GRAPH_FILE.exists():
        try:
            return json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_graph(graph: dict):
    _ensure_dir()
    GRAPH_FILE.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

def update_graph(note_title: str, note_path: str, edges: dict):
    """노트의 지식 그래프 엣지를 업데이트합니다."""
    graph = load_graph()
    all_links = edges.get("explicit_links", []) + edges.get("implicit_links", [])

    if note_title not in graph:
        graph[note_title] = {"edges": [], "type": "note", "note_path": note_path, "implicit_edges": []}

    graph[note_title]["edges"]          = list(set(edges.get("explicit_links", [])))
    graph[note_title]["implicit_edges"] = list(set(edges.get("implicit_links", [])))
    graph[note_title]["note_path"]      = note_path
    graph[note_title]["tags"]           = edges.get("tags", [])

    # 역방향 엣지 등록 (backlinks)
    for link in all_links:
        if link not in graph:
            graph[link] = {"edges": [], "type": "concept", "note_path": "", "implicit_edges": []}
        if "backlinks" not in graph[link]:
            graph[link]["backlinks"] = []
        if note_title not in graph[link]["backlinks"]:
            graph[link]["backlinks"].append(note_title)

    save_graph(graph)
    # 개념도 레지스트리에 등록
    register_concepts(all_links)

def get_graph_stats() -> dict:
    graph = load_graph()
    notes     = [k for k, v in graph.items() if v.get("type") == "note"]
    concepts  = [k for k, v in graph.items() if v.get("type") == "concept"]
    all_edges = sum(len(v.get("edges", [])) + len(v.get("implicit_edges", [])) for v in graph.values())
    return {
        "total_nodes": len(graph),
        "note_nodes":  len(notes),
        "concept_nodes": len(concepts),
        "total_edges": all_edges,
    }


# ── Session Log ───────────────────────────────────────────────────────────────
SESSION_LOG = MEMORY_DIR / "session_log.jsonl"

def log_session(action: str, title: str, input_type: str, note_path: str = ""):
    _ensure_dir()
    entry = {
        "ts": datetime.now().isoformat(),
        "action": action,
        "title": title,
        "type": input_type,
        "path": note_path,
    }
    with open(SESSION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def load_recent_sessions(n: int = 20) -> list:
    if not SESSION_LOG.exists():
        return []
    lines = SESSION_LOG.read_text(encoding="utf-8").strip().split("\n")
    entries = []
    for line in reversed(lines[-100:]):
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries[:n]
