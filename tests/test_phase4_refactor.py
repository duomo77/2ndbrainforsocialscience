"""
test_phase4_refactor.py — Regression tests for audit Phase 4 (Refactor)
========================================================================
Pins:

  F-16/F-07  wikilink centralization golden semantics
  F-07 ADR   PROVIDER_PROFILES behavior equivalence with the old if-chain
  F-10       dead-code deletions are real (modules gone, live path intact)
  C-02       legacy → typed graph migration: idempotent, non-destructive
"""

from __future__ import annotations

import json

import pytest

from core import memory, ros_engine
from core.graph_migration import migrate_legacy_to_typed
from core.knowledge_graph import KnowledgeGraphService, KnowledgeGraphStore
from core.orchestration import ResourceGovernor, get_resource_governor
from core.utils.markdown_utils import count_wikilinks, extract_wikilink_targets


# ══════════════════════════════════════════════════════════════════════════════
# F-16 — unified wikilink semantics
# ══════════════════════════════════════════════════════════════════════════════

class TestWikilinkCentralization:
    def test_plain_link(self):
        assert extract_wikilink_targets("see [[Parallel Trends]] here") == ["Parallel Trends"]

    def test_alias_is_stripped(self):
        assert extract_wikilink_targets("[[DID|difference-in-differences]]") == ["DID"]

    def test_heading_anchor_is_stripped(self):
        assert extract_wikilink_targets("[[Note#Section 2]]") == ["Note"]

    def test_heading_and_alias_combined(self):
        assert extract_wikilink_targets("[[Note#Sec|label]]") == ["Note"]

    def test_multiple_links_per_line(self):
        text = "[[A]] and [[B|beta]] plus [[C#h]]"
        assert extract_wikilink_targets(text) == ["A", "B", "C"]

    def test_malformed_links_are_ignored(self):
        # well-formed but odd content still extracts a stripped target
        assert extract_wikilink_targets("[[unclosed and ]] ]") == ["unclosed and"]
        assert extract_wikilink_targets("no links at all") == []

    def test_count_matches_targets(self):
        text = "[[A]] [[B|b]] [[C#h]]"
        assert count_wikilinks(text) == 3

    def test_graph_edge_extraction_uses_unified_helper(self):
        result = ros_engine.extract_graph_edges(
            "k", "", "model", "# Note\n\nUses [[IV|instrumental variables]] today.")
        assert "IV" in result["explicit_links"]
        assert "IV|instrumental variables" not in result["explicit_links"]


# ══════════════════════════════════════════════════════════════════════════════
# F-07 ADR Stage 1 — provider profile registry equivalence
# ══════════════════════════════════════════════════════════════════════════════

class TestProviderProfiles:
    @pytest.mark.parametrize("base_url,model,expected", [
        ("https://api.deepseek.com/v1", "anything", "deepseek"),
        ("https://dashscope.aliyuncs.com/compatible-mode/v1", "x", "qwen"),
        ("", "qwen-max", "qwen"),
        ("https://open.bigmodel.cn/api", "x", "zhipu"),
        ("", "glm-4-plus", "zhipu"),
        ("https://api.moonshot.ai/v1", "x", "moonshot"),
        ("", "kimi-latest", "moonshot"),
        ("https://api.minimax.chat/v1", "x", "minimax"),
        ("https://qianfan.baidubce.com/v2", "x", "baidu"),
        ("https://api.siliconflow.cn/v1", "x", "siliconflow"),
        ("https://api.lingyiwanwu.com/v1", "x", "01ai"),
        ("https://api.openai.com/v1", "gpt-4o", "openai"),
        ("", "", "openai"),
    ])
    def test_detection_equivalence(self, base_url, model, expected):
        assert ros_engine._detect_provider(base_url, model) == expected

    @pytest.mark.parametrize("provider,expected", [
        ("deepseek", 8192), ("qwen", 8000), ("minimax", 6000),
        ("baidu", 8192), ("openai", 8000), ("unknown", 8000),
    ])
    def test_max_tokens_equivalence(self, provider, expected):
        assert ros_engine._max_tokens(provider) == expected

    def test_qwen3_detection_unchanged(self):
        assert ros_engine._is_qwen3("qwen", "qwen3-4b") is True
        assert ros_engine._is_qwen3("qwen", "qwen-max") is False
        assert ros_engine._is_qwen3("openai", "qwen3-4b") is False


# ══════════════════════════════════════════════════════════════════════════════
# F-10 — dead code is actually gone; live path intact
# ══════════════════════════════════════════════════════════════════════════════

class TestDeadCodeRemoval:
    @pytest.mark.parametrize("module", [
        "core.state_manager", "core.graph_utils", "core.base_provider",
        "core.provider_factory", "core.provider_manager", "core.llm_client",
        "core.chinese_providers", "core.qwen_provider",
        "core.orchestration.QueueOrchestrator",
    ])
    def test_deleted_symbols_are_gone(self, module):
        with pytest.raises((ImportError, AttributeError)):
            if "." in module and not module.startswith("core.orchestration."):
                __import__(module)
            elif module == "core.orchestration.QueueOrchestrator":
                from core import orchestration
                if not hasattr(orchestration, "QueueOrchestrator"):
                    raise AttributeError("QueueOrchestrator removed")

    def test_resource_governor_survives(self):
        assert callable(get_resource_governor)
        governor = get_resource_governor()
        assert isinstance(governor, ResourceGovernor)


# ══════════════════════════════════════════════════════════════════════════════
# C-02 Stage 1 — legacy → typed migration
# ══════════════════════════════════════════════════════════════════════════════

LEGACY_GRAPH = {
    "Paper Note": {
        "type": "note",
        "edges": ["Instrumental Variables", "Parallel Trends"],
        "implicit_edges": ["Econometrics"],
        "note_path": "Papers/Econometrics/Paper Note.md",
        "backlinks": [],
        "tags": ["causal-inference"],
    },
    "Instrumental Variables": {
        "type": "concept", "edges": [], "implicit_edges": [],
        "note_path": "", "backlinks": ["Paper Note"],
    },
    "Parallel Trends": {
        "type": "concept", "edges": [], "implicit_edges": [],
        "note_path": "", "backlinks": ["Paper Note"],
    },
    "Econometrics": {
        "type": "concept", "edges": [], "implicit_edges": [],
        "note_path": "", "backlinks": ["Paper Note"],
    },
}


@pytest.fixture
def migration_env(tmp_path, monkeypatch):
    legacy_file = tmp_path / "legacy_graph.json"
    legacy_file.write_text(json.dumps(LEGACY_GRAPH), encoding="utf-8")
    monkeypatch.setattr(memory, "GRAPH_FILE", legacy_file)
    monkeypatch.setattr(memory, "MEMORY_DIR", tmp_path)

    service = KnowledgeGraphService(KnowledgeGraphStore(tmp_path / "typed_graph.json"))
    sentinel = tmp_path / "sentinel.json"
    return service, sentinel, legacy_file


class TestLegacyMigration:
    def test_migration_moves_nodes_and_edges(self, migration_env):
        service, sentinel, legacy_file = migration_env
        summary = migrate_legacy_to_typed(service=service, sentinel_path=sentinel)

        assert summary["status"] == "migrated"
        assert summary["nodes"] == 4
        assert summary["edges"] == 3  # 2 explicit + 1 implicit
        stats = service.store.stats()
        assert stats["total_nodes"] == 4
        assert stats["total_edges"] == 3
        # legacy file untouched (non-destructive)
        assert json.loads(legacy_file.read_text(encoding="utf-8")) == LEGACY_GRAPH

    def test_migration_is_sentinel_idempotent(self, migration_env):
        service, sentinel, _ = migration_env
        migrate_legacy_to_typed(service=service, sentinel_path=sentinel)
        second = migrate_legacy_to_typed(service=service, sentinel_path=sentinel)
        assert second["status"] == "skipped"

    def test_forced_remigration_does_not_duplicate(self, migration_env):
        service, sentinel, _ = migration_env
        migrate_legacy_to_typed(service=service, sentinel_path=sentinel)
        again = migrate_legacy_to_typed(service=service, sentinel_path=sentinel, force=True)
        assert again["status"] == "migrated"
        stats = service.store.stats()
        assert stats["total_nodes"] == 4, "stable IDs must upsert, not duplicate"
        assert stats["total_edges"] == 3

    def test_empty_legacy_graph_writes_sentinel(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "legacy_graph.json"
        legacy_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(memory, "GRAPH_FILE", legacy_file)
        monkeypatch.setattr(memory, "MEMORY_DIR", tmp_path)
        service = KnowledgeGraphService(KnowledgeGraphStore(tmp_path / "typed.json"))

        summary = migrate_legacy_to_typed(service=service, sentinel_path=tmp_path / "s.json")
        assert summary["status"] == "empty"
        assert (tmp_path / "s.json").exists()
