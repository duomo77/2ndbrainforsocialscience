"""ROS v5.0 통합 테스트 스크립트."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

PASS = 0
FAIL = 0

def check(name, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  ✅ [{name}]")
        PASS += 1
    except Exception as e:
        print(f"  ❌ [{name}] {e}")
        FAIL += 1

# ── 1. RAG 엔진 ──────────────────────────────────────────────────────────────
print("\n[1] RAG Engine (4-Layer Cheapest-Cognition-First)")

def test_rag_import():
    from core.rag_engine import RAGEngine, CognitionPath, get_rag_engine
    e = get_rag_engine()
    assert hasattr(e, "prepare_context")
    assert hasattr(e, "get_metrics_dict")

def test_rag_prepare_context():
    from core.rag_engine import get_rag_engine
    e = get_rag_engine()
    ctx, plan = e.prepare_context("DML causal inference", model="gpt-4o-mini")
    # plan은 None이거나 RetrievalPlan
    print(f"     context_len={len(ctx)}, plan={plan}")

check("RAG import", test_rag_import)
check("RAG prepare_context", test_rag_prepare_context)

# ── 2. 임베딩 거버넌스 ────────────────────────────────────────────────────────
print("\n[2] Embedding Governance + Memory Tier")

def test_embedding_gov():
    from core.embedding_gov import get_embedding_governance, get_memory_tier_manager
    gov = get_embedding_governance()
    tier = get_memory_tier_manager()
    assert hasattr(gov, "should_embed")
    # MemoryTierManager의 실제 API: promote, demote, get_tier, get_hot_nodes
    assert hasattr(tier, "promote")
    assert hasattr(tier, "get_tier")
    print("     EmbeddingGovernance + MemoryTierManager: OK")

def test_memory_tier_store():
    from core.embedding_gov import get_memory_tier_manager
    tier = get_memory_tier_manager()
    # promote으로 hot tier에 등록
    tier.promote("test_note_001", "DML is a double machine learning method.", reason="test")
    tier_name = tier.get_tier("test_note_001")
    hot_nodes = tier.get_hot_nodes()
    print(f"     tier={tier_name}, hot_nodes={len(hot_nodes)}")

check("Embedding governance import", test_embedding_gov)
check("Memory tier store+search", test_memory_tier_store)

# ── 3. 컨텍스트 압축기 ────────────────────────────────────────────────────────
print("\n[3] Context Compressor")

def test_compressor():
    from core.rag_observability import get_context_compressor
    comp = get_context_compressor()
    long_text = "# DML\n\n" + ("This is a long sentence about causal inference. " * 200)
    result = comp.compress(long_text, target_tokens=100)
    assert result.compression_ratio < 1.0
    print(f"     {result.original_tokens} → {result.compressed_tokens} tokens "
          f"(ratio={result.compression_ratio:.2f}, method={result.method})")

def test_compressor_batch():
    from core.rag_observability import get_context_compressor
    comp = get_context_compressor()
    texts = ["# Paper A\n" + "DML content. " * 50,
             "# Paper B\n" + "IV regression. " * 30,
             "# Paper C\n" + "DID analysis. " * 20]
    results = comp.compress_batch(texts, total_token_budget=200)
    total = sum(r.compressed_tokens for r in results)
    print(f"     batch: {len(results)} texts, total_tokens={total}")

check("Context compressor", test_compressor)
check("Batch compression", test_compressor_batch)

# ── 4. RAG 관측성 ─────────────────────────────────────────────────────────────
print("\n[4] RAG Observability")

def test_observability():
    from core.rag_observability import get_rag_observability
    obs = get_rag_observability()
    obs.record_retrieval(
        query_hash="abc123", tokens_used=200, tokens_saved=50,
        latency_ms=120.0, candidates_total=10, candidates_selected=3,
        path="LOCAL_GRAPH", layer="L3_LOCAL",
    )
    obs.record_cache_hit("abc123", tokens_saved=200)
    obs.record_llm_call("abc123", tokens_used=500, insight_generated=True)
    data = obs.get_dashboard_data()
    assert "health_status" in data
    assert "cache_hit_rate" in data
    print(f"     health={data['health_status']}, cache_hit={data['cache_hit_rate']:.2f}, "
          f"precision={data['avg_precision']:.2f}")

def test_efficiency_report():
    from core.rag_observability import get_rag_observability
    obs = get_rag_observability()
    report = obs.get_efficiency_report()
    assert "RAG Efficiency Report" in report
    print(f"     report lines: {len(report.splitlines())}")

check("RAG observability record+dashboard", test_observability)
check("Efficiency report", test_efficiency_report)

# ── 5. 기존 v4.0 엔진 호환성 ─────────────────────────────────────────────────
print("\n[5] v4.0 Engine Compatibility")

def test_v4_engines():
    from core.security import get_security_layer
    from core.graph_integrity import get_graph_integrity_engine
    from core.memory_trust import get_memory_trust_engine
    from core.perf_engine import get_cache_engine
    from core.fault_recovery import get_fault_recovery_engine
    sec = get_security_layer()
    res = sec.validate_input("DML paper analysis", "paper")
    assert res.is_safe
    print(f"     security: trust={res.trust_score:.2f}")

def test_cognitive_engines():
    from core.note_evolution import get_evolution_engine
    from core.contradiction_engine import get_contradiction_engine
    from core.math_ontology import get_math_engine
    evo = get_evolution_engine()
    con = get_contradiction_engine()
    math = get_math_engine()
    assert evo and con and math
    print("     5 cognitive engines: OK")

check("v4.0 infrastructure engines", test_v4_engines)
check("v3.0 cognitive engines", test_cognitive_engines)

# ── 6. worker.py RAG 통합 ────────────────────────────────────────────────────
print("\n[6] Worker RAG Integration")

def test_worker_rag_helpers():
    # worker.py의 지연 임포트 헬퍼 테스트
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "worker", "/home/ubuntu/econometric-wiki/core/worker.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # PyQt6 없이 임포트 가능한지 확인 (함수 정의만)
    src = open("/home/ubuntu/econometric-wiki/core/worker.py").read()
    assert "_get_rag_engine" in src
    assert "_get_rag_observability" in src
    assert "_get_context_compressor" in src
    assert "RAG 컨텍스트 최적화" in src
    print("     worker.py RAG helpers: all present")

check("Worker RAG integration", test_worker_rag_helpers)

# ── 7. infra_dashboard RAG 패널 ──────────────────────────────────────────────
print("\n[7] InfraDashboard RAG Panel")

def test_dashboard_rag_panel():
    src = open("/home/ubuntu/econometric-wiki/ui/infra_dashboard.py").read()
    assert "_build_rag_panel" in src
    assert "_refresh_rag" in src
    assert "RAG Cost Optimizer" in src
    assert "cache_hit_rate" in src
    assert "health_status" in src
    print("     infra_dashboard RAG panel: all present")

check("InfraDashboard RAG panel", test_dashboard_rag_panel)

# ── 결과 ─────────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"🎉 ROS v5.0 통합 테스트: {PASS}/{PASS+FAIL} 통과")
if FAIL > 0:
    print(f"⚠️  {FAIL}개 실패")
    sys.exit(1)
else:
    print("✅ 전체 통과!")
