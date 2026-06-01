from core.rag_engine import HierarchicalRetriever, RetrievalLayer


def test_atomic_retrieval_reads_bounded_number_of_files(tmp_path, monkeypatch):
    for i in range(100):
        (tmp_path / f"note-{i}.md").write_text(
            f"# Causal Note {i}\n\ncausal inference identification treatment outcome",
            encoding="utf-8",
        )

    read_count = 0
    original = type(tmp_path).read_text

    def counted_read_text(self, *args, **kwargs):
        nonlocal read_count
        read_count += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "read_text", counted_read_text)

    retriever = HierarchicalRetriever(str(tmp_path))
    candidates = retriever._retrieve_layer(
        "causal identification",
        RetrievalLayer.L4_ATOMIC,
        max_count=5,
        token_budget=1000,
    )

    assert len(candidates) <= 5
    assert read_count <= 15


def test_atomic_retrieval_skips_huge_files(tmp_path):
    huge = tmp_path / "huge.md"
    huge.write_text("causal " * 300_000, encoding="utf-8")
    small = tmp_path / "small.md"
    small.write_text("causal identification", encoding="utf-8")

    retriever = HierarchicalRetriever(str(tmp_path))
    candidates = retriever._retrieve_layer(
        "causal identification",
        RetrievalLayer.L4_ATOMIC,
        max_count=5,
        token_budget=1000,
    )

    assert [c.node_id for c in candidates] == ["small.md"]
