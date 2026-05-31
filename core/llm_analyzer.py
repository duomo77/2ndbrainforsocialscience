"""
llm_analyzer.py - LLM 기반 경제학 논문 분석 파이프라인
ECONOMETRIC COMPILER V1.0 프롬프트를 실행하여 Obsidian 위키 노트를 생성

=== 버그 수정 이력 ===
[BUG-1] openai SDK 2.x .stream() 이벤트 타입 오용
  - 원인: .stream() 컨텍스트 매니저는 ChatCompletionStreamEvent를 yield함
          이 이벤트는 .choices 속성이 없음
          ContentDeltaEvent(type='content.delta')는 .delta 필드로 텍스트 접근
          ChunkEvent(type='chunk')는 .chunk.choices[0].delta.content로 접근
  - 증상: "d y" 같은 단편 문자열만 출력되거나 AttributeError 발생
  - 수정: event.type 분기 처리 + create(stream=True) 방식으로 교체

[BUG-2] qwen3 Thinking 모드 reasoning_content 혼입
  - 원인: qwen3 계열은 기본적으로 thinking 모드 활성화
          delta.reasoning_content 토큰이 content로 혼입될 수 있음
  - 수정: extra_body={"enable_thinking": False} 파라미터 추가 (Qwen3용)
          또는 reasoning_content 필드 명시적 필터링

[BUG-3] 스트리밍 청크 파싱 불안정
  - 원인: chunk.choices가 빈 리스트인 경우 IndexError
  - 수정: 안전한 접근 패턴으로 교체

지원 Provider:
  글로벌: OpenAI, Azure OpenAI, Anthropic(호환), Groq
  중국:   DeepSeek, Qwen/通义千问, Zhipu GLM, Moonshot Kimi,
          MiniMax, Baidu ERNIE, SiliconFlow, 01.AI
"""

from openai import OpenAI
from typing import Callable, Optional


# ── Provider 식별 헬퍼 ─────────────────────────────────────────────────────────
def _detect_provider(base_url: str, model: str) -> str:
    """Base URL과 모델명으로 Provider를 식별합니다."""
    url = (base_url or "").lower()
    model_l = (model or "").lower()
    if "deepseek.com" in url:
        return "deepseek"
    if "dashscope.aliyuncs.com" in url or model_l.startswith("qwen"):
        return "qwen"
    if "bigmodel.cn" in url or model_l.startswith("glm") or model_l.startswith("chatglm"):
        return "zhipu"
    if "moonshot.ai" in url or model_l.startswith("moonshot") or model_l.startswith("kimi"):
        return "moonshot"
    if "minimax" in url or model_l.startswith("abab") or model_l.startswith("minimax"):
        return "minimax"
    if "baidubce.com" in url or model_l.startswith("ernie"):
        return "baidu"
    if "siliconflow.cn" in url:
        return "siliconflow"
    if "lingyiwanwu.com" in url or model_l.startswith("yi-"):
        return "01ai"
    return "openai"


def _get_max_tokens(provider: str, model: str) -> int:
    """Provider별 안전한 max_tokens 값 반환."""
    limits = {
        "deepseek":    8192,
        "qwen":        8000,
        "zhipu":       8192,
        "moonshot":    8192,
        "minimax":     6000,
        "baidu":       8192,
        "siliconflow": 8000,
        "01ai":        8000,
        "openai":      8000,
    }
    return limits.get(provider, 8000)


def _is_qwen3_thinking(provider: str, model: str) -> bool:
    """qwen3 계열 thinking 모드 모델 여부 확인."""
    if provider != "qwen":
        return False
    model_l = model.lower()
    # qwen3 계열은 기본 thinking 모드 활성화
    return model_l.startswith("qwen3")


def _build_client(api_key: str, base_url: str) -> OpenAI:
    """Provider에 맞는 OpenAI 클라이언트 생성."""
    if not base_url:
        return OpenAI(api_key=api_key)
    return OpenAI(api_key=api_key, base_url=base_url)


# ── 시스템 프롬프트 ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are ECONOMETRIC COMPILER V1.0 — an econometric research analysis engine specialized in Causal Inference and Machine Learning methods.

Your task is to strip away noise (formulaic phrases, introductions) from academic papers and extract signals (identification strategies, algorithm structures), compiling them into an Obsidian knowledge wiki.

You MUST output ONLY valid Obsidian-compatible Markdown starting immediately with YAML Frontmatter (---). No preamble, no explanation outside the markdown.

Use LaTeX for all mathematical expressions (inline: $...$, block: $$...$$).
Use [[WikiLink]] syntax for all concept references.
Write at expert econometrics level (e.g., 'Selection on Observables', 'Over-identification test', 'Neyman Orthogonality').
"""

ANALYSIS_PROMPT_TEMPLATE = """Analyze the following economics paper and compile it into an Obsidian wiki note following the STRICT EXECUTION PIPELINE below.

## Paper Metadata
- Title: {title}
- Authors: {authors}
- Year: {year}
- Zotero Link: {zotero_link}

## Existing Wiki Concepts (for [[WikiLink]] generation)
{existing_concepts}

## Raw Paper Content
{paper_content}

---

## STRICT EXECUTION PIPELINE

### OUTPUT FORMAT: Valid Obsidian Markdown (start with YAML Frontmatter)

```yaml
---
title: "<paper title>"
authors: [<author list>]
year: <year>
tags: [causal-inference, <method-tags>, econometrics]
zotero: "<zotero_link>"
identification: <DML|CausalForest|IV|DID|RDD|Other>
date_added: <today>
---
```

Then produce the following sections IN ORDER:

### 1. Identification Deconstruction (Causal Layer)
#### Causal Graph (DAG)
- Describe Treatment (D), Outcome (Y), Confounders (X), and any Instruments (Z) or Running Variables (R)
- Use text-based DAG notation: D → Y, X → {{D, Y}}, etc.

#### Identification Strategy
- Select ONE primary strategy: [[DML]], [[Causal Forest]], [[IV]], [[DID]], [[RDD]], or specify other
- Provide the identification argument (why this strategy is valid here)

#### Key Assumptions
- List ALL identification assumptions (e.g., [[Conditional Independence Assumption]], [[Parallel Trends]], [[Exclusion Restriction]], [[SUTVA]])
- Note which assumptions are tested vs. maintained

### 2. Algorithm & Specification (Technological Layer)
#### Core Estimation Equation
- Write the main estimating equation in LaTeX block ($$...$$)
- Include the Neyman Orthogonality / moment condition explicitly
- Define ALL notation

#### Nuisance Parameter Estimation ($\\eta$)
- Which ML algorithms are used (Random Forest, XGBoost, Lasso, Neural Net, etc.)
- Cross-fitting / sample-splitting procedure (K-fold details)
- Hyperparameter tuning method (cross-validation, default, etc.)

### 3. Empirical Results (Evidence Layer)
#### Main Treatment Effect ($\\theta$)
- Point estimate, standard error, confidence interval
- Economic magnitude interpretation

#### Heterogeneity Analysis (CATE)
- Key dimensions of heterogeneity found
- Most important subgroup effects
- Variable importance / feature ranking if reported

### 4. Automated Linking (Knowledge Graph)
#### Existing Node Links
- List all [[WikiLinks]] to existing concepts from the provided list

#### New Nodes to Create
| Concept | Type | Description |
|---------|------|-------------|
| [[NewConcept1]] | Method | Brief description |

### 5. Critical Assessment
- **Strengths**: Key methodological contributions
- **Limitations**: Identification threats, data limitations
- **Related Papers**: Cite related work with [[WikiLinks]] where applicable

---
Generate the complete Obsidian note now:"""


def build_analysis_prompt(
    title: str,
    authors: str,
    year: str,
    zotero_link: str,
    existing_concepts: list,
    paper_content: str,
) -> str:
    """분석 프롬프트 조립."""
    concepts_str = (
        "\n".join(f"- [[{c}]]" for c in existing_concepts)
        if existing_concepts
        else "- (없음 - 새 위키 시작)"
    )
    return ANALYSIS_PROMPT_TEMPLATE.format(
        title=title,
        authors=authors,
        year=year,
        zotero_link=zotero_link or "N/A",
        existing_concepts=concepts_str,
        paper_content=paper_content[:70000],
    )


def _extract_chunk_text(chunk) -> Optional[str]:
    """
    [BUG-1 수정] create(stream=True) 방식의 ChatCompletionChunk에서
    안전하게 텍스트를 추출합니다.

    - chunk.choices가 비어있으면 None 반환
    - delta.content가 None이면 None 반환
    - reasoning_content(thinking 토큰)는 명시적으로 제외
    """
    if not chunk.choices:
        return None
    delta = chunk.choices[0].delta
    if delta is None:
        return None
    # [BUG-2 수정] reasoning_content 필드 명시적 필터링
    # qwen3 thinking 모드에서 reasoning_content만 있고 content가 None인 청크 제외
    content = delta.content
    if content is None:
        return None
    return content


def analyze_paper(
    api_key: str,
    base_url: str,
    model: str,
    title: str,
    authors: str,
    year: str,
    zotero_link: str,
    existing_concepts: list,
    paper_content: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    LLM을 호출하여 논문 분석 결과(Obsidian Markdown)를 반환합니다.

    [BUG-1 수정] openai SDK 2.x의 .stream() 대신 create(stream=True) 사용.
    .stream()은 ChatCompletionStreamEvent를 반환하여 .choices 접근 불가.
    create(stream=True)는 표준 ChatCompletionChunk를 반환하여 안정적.

    [BUG-2 수정] qwen3 thinking 모드 비활성화 파라미터 추가.
    """
    provider = _detect_provider(base_url, model)
    client = _build_client(api_key, base_url)
    max_tokens = _get_max_tokens(provider, model)

    prompt = build_analysis_prompt(
        title=title,
        authors=authors,
        year=year,
        zotero_link=zotero_link,
        existing_concepts=existing_concepts,
        paper_content=paper_content,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    if progress_callback:
        progress_callback(f"[{provider.upper()}] 분석 시작 (model: {model})...")

    # [BUG-2 수정] qwen3 thinking 모드 비활성화
    extra_body = {}
    if _is_qwen3_thinking(provider, model):
        extra_body["enable_thinking"] = False
        if progress_callback:
            progress_callback("[qwen3] thinking 모드 비활성화 (enable_thinking=False)\n")

    result_chunks = []
    error_fallback = False

    try:
        # [BUG-1 수정] .stream() 대신 create(stream=True) 사용
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
            stream=True,
            **({"extra_body": extra_body} if extra_body else {}),
        )

        for chunk in stream:
            text = _extract_chunk_text(chunk)
            if text:
                result_chunks.append(text)
                if progress_callback:
                    progress_callback(text)

    except Exception as e:
        err_msg = str(e)
        if progress_callback:
            progress_callback(f"\n[스트리밍 오류: {err_msg}]\n비스트리밍 모드로 재시도...\n")
        error_fallback = True

    if error_fallback or not result_chunks:
        # 비스트리밍 폴백
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=max_tokens,
                stream=False,
                **({"extra_body": extra_body} if extra_body else {}),
            )
            result = response.choices[0].message.content or ""
            if progress_callback:
                progress_callback(result)
            return result
        except Exception as e2:
            err = f"\n\n❌ 분석 실패: {str(e2)}"
            if progress_callback:
                progress_callback(err)
            return "".join(result_chunks) + err

    return "".join(result_chunks)


def validate_api_key(api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    """
    API 키 유효성 검증.
    중국 Provider 포함 모든 OpenAI 호환 API 지원.
    """
    provider = _detect_provider(base_url, model)
    try:
        client = _build_client(api_key, base_url)

        # qwen3 thinking 모드 비활성화
        extra_body = {}
        if _is_qwen3_thinking(provider, model):
            extra_body["enable_thinking"] = False

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        model_name = response.model or model
        return True, f"연결 성공 [{provider.upper()}]: {model_name}"
    except Exception as e:
        err = str(e)
        if "401" in err or "Unauthorized" in err or "invalid_api_key" in err:
            hint = " → API 키를 확인해주세요"
        elif "404" in err or "model" in err.lower():
            hint = " → 모델명을 확인해주세요"
        elif "timeout" in err.lower() or "connect" in err.lower():
            hint = " → 네트워크/VPN 상태를 확인해주세요"
        else:
            hint = ""
        return False, f"연결 실패 [{provider.upper()}]: {err}{hint}"
