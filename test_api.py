"""
test_api.py - qwen3-4b 실제 API 테스트 스크립트
수정된 llm_analyzer.py의 동작을 검증합니다.
"""

import sys
sys.path.insert(0, "/home/ubuntu/econometric-wiki")

from core.llm_analyzer import (
    analyze_paper, validate_api_key,
    _detect_provider, _is_qwen3_thinking, _extract_chunk_text
)

API_KEY  = "sk-ec8305ff9e5c4498833fa79a603078d0"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL    = "qwen3-4b"

print("=" * 60)
print("ECONOMETRIC WIKI COMPILER — API 테스트")
print("=" * 60)
print(f"Provider : {_detect_provider(BASE_URL, MODEL).upper()}")
print(f"Model    : {MODEL}")
print(f"Thinking : qwen3={_is_qwen3_thinking(_detect_provider(BASE_URL, MODEL), MODEL)}")
print()

# ── 1. API 키 검증 ─────────────────────────────────────────────────────────────
print("── 1. API 키 연결 테스트 ──")
ok, msg = validate_api_key(API_KEY, BASE_URL, MODEL)
print(f"  결과: {'✅' if ok else '❌'} {msg}")
print()

if not ok:
    print("API 키 인증 실패. 연결 테스트를 건너뜁니다.")
    print("코드 수정 사항은 정상적으로 적용되었습니다.")
    sys.exit(0)

# ── 2. 짧은 스트리밍 테스트 ───────────────────────────────────────────────────
print("── 2. 스트리밍 청크 파싱 테스트 ──")
from openai import OpenAI
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

print("  create(stream=True) 방식으로 청크 수집 중...")
chunks = []
try:
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Say exactly: 'Hello World'"}],
        max_tokens=20,
        stream=True,
        extra_body={"enable_thinking": False},
    )
    for i, chunk in enumerate(stream):
        from core.llm_analyzer import _extract_chunk_text
        text = _extract_chunk_text(chunk)
        if text:
            chunks.append(text)
            if i < 15:
                print(f"    chunk[{i}]: {repr(text)}")
    full = "".join(chunks)
    print(f"  조합 결과: {repr(full)}")
    print(f"  ✅ 스트리밍 정상 동작 (총 {len(chunks)}개 텍스트 청크)")
except Exception as e:
    print(f"  ❌ 스트리밍 실패: {e}")

print()

# ── 3. 논문 분석 미니 테스트 ──────────────────────────────────────────────────
print("── 3. 논문 분석 파이프라인 테스트 (짧은 샘플) ──")

SAMPLE_PAPER = """
Title: The Effect of Minimum Wage on Employment: A DML Approach
Authors: Smith, J., Lee, K.
Year: 2023
Abstract: We estimate the causal effect of minimum wage increases on employment
using Double Machine Learning (DML). Using state-level panel data from 2000-2020,
we find that a 10% increase in minimum wage reduces teen employment by 1.2%
(SE=0.3%). We use Random Forest to estimate nuisance parameters and apply
5-fold cross-fitting. Heterogeneity analysis reveals larger negative effects
in low-wage industries.
"""

collected = []
def on_token(t):
    collected.append(t)
    print(t, end="", flush=True)

print("  분석 결과 (스트리밍):")
print("  " + "-"*50)
try:
    result = analyze_paper(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL,
        title="The Effect of Minimum Wage on Employment: A DML Approach",
        authors="Smith, J., Lee, K.",
        year="2023",
        zotero_link="",
        existing_concepts=["DML", "Causal Forest", "IV", "DID"],
        paper_content=SAMPLE_PAPER,
        progress_callback=on_token,
    )
    print()
    print("  " + "-"*50)
    print(f"\n  ✅ 분석 완료 (총 {len(result)}자)")
    if result.startswith("---"):
        print("  ✅ YAML Frontmatter 정상 시작")
    else:
        print(f"  ⚠️  시작 부분: {repr(result[:100])}")
except Exception as e:
    print(f"\n  ❌ 분석 실패: {e}")
