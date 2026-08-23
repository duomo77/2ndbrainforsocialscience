"""
test_phase3_correct.py — Regression tests for audit Phase 3 (Correct)
======================================================================
Pins:

  B-05b     SafeMode template no longer crashes on {}/} in titles/content
  Lead §16  mid-stream truncation discarded; complete streams returned
  C-01      rag_context reaches the analysis prompt with untrusted delimiter
  C-04      lineage upsert-by-title; self-parent exclusion
  B-11/C-11 evolution version stays stable for unchanged content
  F-13      worker single-flight guard
"""

from __future__ import annotations

from core import ros_engine
from core.fault_recovery import SafeMode
from core.idea_lineage import IdeaLineageEngine
from core.note_evolution import NoteEvolutionEngine


# ══════════════════════════════════════════════════════════════════════════════
# B-05b — SafeMode template hardening
# ══════════════════════════════════════════════════════════════════════════════

class TestSafeModeTemplate:
    def test_curly_brace_title_does_not_crash(self):
        note = SafeMode().generate_fallback_note(
            title="{Market} Design: {beta} estimation",
            content="Some {content} with } unbalanced braces",
            input_type="paper",
            error_reason="timeout",
        )
        assert "{Market} Design: {beta} estimation" in note
        assert "safe_mode: true" in note

    def test_template_contains_no_format_placeholders(self):
        # str.format-style braces would reintroduce the crash class
        assert "{" not in SafeMode.SAFE_MODE_TEMPLATE
        assert "}" not in SafeMode.SAFE_MODE_TEMPLATE

    def test_all_sentinels_are_substituted(self):
        note = SafeMode().generate_fallback_note(
            title="T", content="C", input_type="notes", error_reason="E")
        assert "@@" not in note, "every sentinel must be replaced"


# ══════════════════════════════════════════════════════════════════════════════
# Lead §16 — streaming truncation guard
# ══════════════════════════════════════════════════════════════════════════════

class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content=None, finish_reason=None):
        self.delta = _Delta(content)
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, content=None, finish_reason=None):
        self.choices = [_Choice(content, finish_reason)]


class _NonStreamResponse:
    def __init__(self, text):
        self.choices = [type("M", (), {"message": type("C", (), {"content": text})()})]


class _FakeCompletions:
    def __init__(self, stream_chunks, nonstream_text):
        self.stream_chunks = stream_chunks
        self.nonstream_text = nonstream_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return list(self.stream_chunks)
        return _NonStreamResponse(self.nonstream_text)


class _FakeClient:
    def __init__(self, stream_chunks, nonstream_text):
        self.chat = type("Chat", (), {
            "completions": _FakeCompletions(stream_chunks, nonstream_text)
        })()


class TestStreamCompletionGuard:
    def test_stream_ending_without_finish_reason_falls_back(self):
        # provider closes the stream early — chunks exist but no finish_reason
        client = _FakeClient(
            [_Chunk("partial "), _Chunk("text")],
            nonstream_text="FULL COMPLETE RESULT",
        )
        result = ros_engine._call_llm(
            client, "model-x", "openai",
            [{"role": "user", "content": "hi"}], 100)
        assert result == "FULL COMPLETE RESULT", \
            "partial stream without finish_reason must not be returned as complete"

    def test_complete_stream_is_returned_directly(self):
        client = _FakeClient(
            [_Chunk("STREAM"), _Chunk("ED", finish_reason="stop")],
            nonstream_text="SHOULD NOT BE USED",
        )
        result = ros_engine._call_llm(
            client, "model-x", "openai",
            [{"role": "user", "content": "hi"}], 100)
        assert result == "STREAMED"
        # exactly one API call — no redundant non-stream retry
        assert len(client.chat.completions.calls) == 1


# ══════════════════════════════════════════════════════════════════════════════
# C-01 — retrieved context reaches the prompt
# ══════════════════════════════════════════════════════════════════════════════

class TestRagContextWiring:
    def _capture_prompt(self, monkeypatch, call):
        captured = {}

        def fake_call_llm(client, model, provider, messages, max_tok,
                          callback=None, is_cancelled=None):
            captured["messages"] = messages
            return "NOTE"

        monkeypatch.setattr(ros_engine, "_call_llm", fake_call_llm)
        call()
        return captured["messages"][1]["content"]

    def test_paper_prompt_contains_rag_context_with_untrusted_delimiter(self, monkeypatch):
        prompt = self._capture_prompt(monkeypatch, lambda: ros_engine.analyze_paper(
            api_key="k", base_url="", model="m",
            title="T", authors="A", year="2020", journal="J", zotero="",
            existing_nodes=[], researcher_profile={},
            content="body text", rag_context="MARKER_CTX_123",
        ))
        assert "MARKER_CTX_123" in prompt
        assert "untrusted" in prompt.lower()
        assert "NOT instructions" in prompt

    def test_notes_prompt_omits_context_block_when_absent(self, monkeypatch):
        prompt = self._capture_prompt(monkeypatch, lambda: ros_engine.analyze_notes(
            api_key="k", base_url="", model="m",
            context="", existing_nodes=[], researcher_profile={},
            content="body text",
        ))
        assert "Retrieved Context" not in prompt

    def test_equation_prompt_accepts_rag_context(self, monkeypatch):
        prompt = self._capture_prompt(monkeypatch, lambda: ros_engine.analyze_equation(
            api_key="k", base_url="", model="m",
            context="", researcher_profile={},
            content="x = y", rag_context="EQ_CTX_456",
        ))
        assert "EQ_CTX_456" in prompt


# ══════════════════════════════════════════════════════════════════════════════
# C-04 — lineage idempotency + self-link exclusion
# ══════════════════════════════════════════════════════════════════════════════

class TestLineageIdempotency:
    def test_reregistration_updates_instead_of_duplicating(self, tmp_path):
        eng = IdeaLineageEngine(data_dir=tmp_path)
        first = eng.register_idea(title="Idea A", content="version one")
        second = eng.register_idea(title="Idea A", content="version one")

        assert first.lineage_id == second.lineage_id
        assert len(eng.store.all_nodes()) == 1, "re-analysis must not duplicate roots"

    def test_content_change_is_tracked_on_same_node(self, tmp_path):
        eng = IdeaLineageEngine(data_dir=tmp_path)
        first = eng.register_idea(title="Idea A", content="version one")
        updated = eng.register_idea(title="Idea A", content="version two, revised")

        assert updated.lineage_id == first.lineage_id
        assert updated.content_hash != first.content_hash

    def test_self_parent_is_excluded(self, tmp_path):
        eng = IdeaLineageEngine(data_dir=tmp_path)
        node = eng.register_idea(
            title="Idea B", content="x", parent_titles=["Idea B"])
        assert node.parent_ids == [], "a note cannot be its own ancestor"

    def test_real_parent_links_still_work(self, tmp_path):
        eng = IdeaLineageEngine(data_dir=tmp_path)
        parent = eng.register_idea(title="Parent Idea", content="p")
        child = eng.register_idea(
            title="Child Idea", content="c", parent_titles=["Parent Idea"])
        assert child.parent_ids == [parent.lineage_id]
        assert child.lineage_id in eng.store.get_node(parent.lineage_id).child_ids


# ══════════════════════════════════════════════════════════════════════════════
# B-11/C-11 — evolution version stability
# ══════════════════════════════════════════════════════════════════════════════

class TestEvolutionVersionStability:
    def test_identical_reregistration_does_not_inflate_version(self, tmp_path):
        eng = NoteEvolutionEngine(data_dir=tmp_path)
        r1 = eng.register_note("Note X", "some short content", ["L1", "L2"])
        r2 = eng.register_note("Note X", "some short content", ["L1", "L2"])
        assert r2.version == r1.version, "same content must not bump version"

    def test_content_change_bumps_version_once(self, tmp_path):
        eng = NoteEvolutionEngine(data_dir=tmp_path)
        r1 = eng.register_note("Note X", "some short content", ["L1", "L2"])
        r2 = eng.register_note("Note X", "revised and expanded content", ["L1"])
        assert r2.version == r1.version + 1


# ══════════════════════════════════════════════════════════════════════════════
# F-13 — worker single-flight guard
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkerLifecycle:
    def test_single_flight_guard_blocks_second_start(self, qt_app, monkeypatch):
        from ui.main_window import MainWindow

        window = MainWindow()
        try:
            assert hasattr(window, "_analyze_action"), "toolbar action must be tracked"

            class FakeRunningWorker:
                def isRunning(self):
                    return True

            window._worker = FakeRunningWorker()

            dialogs = []
            monkeypatch.setattr(
                "ui.main_window.QMessageBox.information",
                staticmethod(lambda *a, **k: dialogs.append(a)))

            # Guard fires before any config/UI mutation — must return early
            window._start_analysis()

            assert dialogs, "guard must inform the user"
            assert not hasattr(window, "_started_new_worker")
        finally:
            window.deleteLater()
