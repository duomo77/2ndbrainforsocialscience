"""
ros_engine.py  —  ROS v7.0 Universal Science Cognition Engine
==============================================================
철학: AI-Native Scientific Cognition OS
      - 그래프-네이티브 인지 엔진
      - 의미론적 메모리 인프라
      - 분산 과학 추론 시스템
      - 멀티-에피스테믹 지원 (실증주의 / 해석주의 / 구성주의 / 비판이론)

지원 분야: 자연과학·사회과학·공학·의학·인문학·학제간 연구 전 분야
"""
from __future__ import annotations

from openai import OpenAI
from typing import Callable, Optional
import json
import re


# ── Provider 감지 ──────────────────────────────────────────────────────────────
def _detect_provider(base_url: str, model: str) -> str:
    url = (base_url or "").lower()
    m   = (model or "").lower()
    if "deepseek.com"           in url: return "deepseek"
    if "dashscope.aliyuncs.com" in url: return "qwen"
    if m.startswith("qwen"):            return "qwen"
    if "bigmodel.cn"            in url: return "zhipu"
    if m.startswith("glm"):             return "zhipu"
    if "moonshot.ai"            in url: return "moonshot"
    if m.startswith("kimi"):            return "moonshot"
    if "minimax"                in url: return "minimax"
    if "baidubce.com"           in url: return "baidu"
    if "siliconflow.cn"         in url: return "siliconflow"
    if "lingyiwanwu.com"        in url: return "01ai"
    return "openai"

def _is_qwen3(provider: str, model: str) -> bool:
    return provider == "qwen" and (model or "").lower().startswith("qwen3")

def _max_tokens(provider: str) -> int:
    return {"deepseek":8192,"qwen":8000,"zhipu":8192,"moonshot":8192,
            "minimax":6000,"baidu":8192,"siliconflow":8000,"01ai":8000}.get(provider, 8000)

def _build_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

def _extract_text(chunk) -> Optional[str]:
    if not chunk.choices: return None
    delta = chunk.choices[0].delta
    return delta.content if delta and delta.content else None


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        clean = (value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MASTER SYSTEM PROMPT — ROS v7.0 Universal Science OS
# ══════════════════════════════════════════════════════════════════════════════

ROS_SYSTEM_PROMPT = """You are the Research Operating System (ROS) v7.0 — an AI-Native Scientific Cognition OS.

## IDENTITY
You are NOT a summarization tool, chatbot, or note-taking assistant.
You ARE:
- A graph-native cognition engine
- A semantic memory infrastructure
- A distributed scientific reasoning system
- A multi-epistemic research environment

## CORE PHILOSOPHY
Goal: preserve stable scientific cognition across time.
Optimize for: semantic durability · epistemic integrity · graph survivability · cognitive sustainability

## MULTI-EPISTEMIC SUPPORT
You MUST support ALL epistemic traditions equally:
- Positivist / Quantitative reasoning (econometrics, statistics, experiments)
- Interpretivist / Qualitative reasoning (ethnography, discourse, narrative)
- Constructivist reasoning (social construction, institutional analysis)
- Critical theory (power, ideology, structural critique)
- Mixed-method integration
- Historical / Comparative reasoning
- Computational / Data-driven reasoning

You MUST NEVER assume all knowledge reduces to optimization, econometrics, or prediction.
Preserve epistemic diversity.

## SUPPORTED DISCIPLINES
Natural Sciences: Physics, Chemistry, Biology, Mathematics, Statistics, Astronomy, Earth Science, Environmental Science, Neuroscience, Genetics, Ecology, Materials Science
Social Sciences: Economics, Econometrics, Psychology, Sociology, Political Science, Anthropology, Geography, Communication Studies, Law, Education
Engineering & Technology: Computer Science, Machine Learning, Electrical Engineering, Mechanical Engineering, Chemical Engineering, Civil Engineering, Robotics, Bioinformatics
Medical & Health: Medicine, Public Health, Epidemiology, Pharmacology, Clinical Trials, Psychiatry
Humanities: History, Philosophy, Linguistics, Literature, Art History
Interdisciplinary: Cognitive Science, Behavioral Economics, Data Science, Complex Systems

## OUTPUT RULES
1. Output ONLY valid Obsidian-compatible Markdown starting with YAML frontmatter (---)
2. Use [[WikiLink]] for ALL concept references — papers, methods, datasets, authors, equations, theories
3. Use LaTeX for ALL math: inline $...$ and block $$...$$
4. Never generate shallow summaries — always prioritize abstraction and reusable insight
5. Every note must have: tags, aliases, connections, open questions, epistemic_mode
6. Adapt depth and framing to the discipline and epistemic tradition of the input
7. Identify: assumptions, theoretical tensions, methodological weaknesses, extension opportunities"""


# ══════════════════════════════════════════════════════════════════════════════
# DISCIPLINE-AWARE PAPER ANALYSIS PROMPT
# ══════════════════════════════════════════════════════════════════════════════

PAPER_PROMPT = """INPUT TYPE: Academic Paper
DISCIPLINE: {discipline}
EPISTEMIC MODE: {epistemic_mode}
TASK: Transform into atomic Obsidian knowledge primitives.

Paper Metadata:
- Title: {title}
- Authors: {authors}
- Year: {year}
- Journal: {journal}
- Zotero: {zotero}

Existing Knowledge Graph Nodes:
{existing_nodes}

Researcher Profile & Interests:
{researcher_profile}

Paper Content:
{content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT: Complete Obsidian note. Start immediately with ---

YAML frontmatter must include:
  title, authors, year, journal, discipline, epistemic_mode,
  tags, aliases, type: paper, status: processed

Then adapt sections based on EPISTEMIC MODE:

=== IF epistemic_mode = quantitative ===

## 🎯 Research Question & Contribution
- Core question (1 sentence, precise)
- Marginal contribution over prior literature

## 🔗 Causal / Statistical Architecture
### Identification / Estimation Strategy
- Strategy: [[DML]] / [[IV]] / [[DID]] / [[RDD]] / [[RCT]] / [[Regression]] / [[Bayesian]] / other
- Key assumptions and their validity
- Identification threats

### Core Equation
$$[main estimating equation]$$

### Algorithm & Nuisance Parameters
| Component | Algorithm | Tuning |
|-----------|-----------|--------|

## 📊 Data Architecture
- Source, N, T, unit of observation
- Treatment/outcome/control structure

## 📈 Results
### Main Effect
- Estimate ± SE, [CI], p-value, magnitude

### Heterogeneity
- Key subgroups, CATE patterns

## ⚠️ Critical Assessment
- Identification threats
- Methodological weaknesses
- Proposed robustness checks: [ ]

=== IF epistemic_mode = qualitative ===

## 🎯 Research Question & Contribution
- Core interpretive question
- Contribution to theoretical/conceptual understanding

## 🔍 Theoretical Framework
- Paradigm: [[Interpretivism]] / [[Constructivism]] / [[Critical Theory]] / other
- Key theoretical concepts and their definitions
- Ontological and epistemological assumptions

## 🗣️ Methodology
- Method: [[Ethnography]] / [[Grounded Theory]] / [[Discourse Analysis]] / [[Interview]] / [[Case Study]] / other
- Data collection: participants, sites, duration
- Analytical approach: thematic coding / constant comparison / etc.

## 💡 Key Findings (Thematic)
### Theme 1: [Name]
> [Core finding]
- Evidence: [quotes/observations]
- Connects to: [[concept1]], [[concept2]]

## 🔗 Theoretical Connections
- Extends: [[theory/author]]
- Challenges: [[theory/author]]
- Synthesizes: [[concept1]] + [[concept2]]

## ⚠️ Reflexivity & Limitations
- Researcher positionality
- Transferability considerations
- Trustworthiness criteria (credibility/dependability/confirmability)

=== IF epistemic_mode = mixed ===

## 🎯 Research Question & Contribution
## 🔀 Mixed-Method Design
- QUAN component: [design, N, analysis]
- QUAL component: [design, participants, analysis]
- Integration strategy: triangulation / sequential / embedded

## 📊 Quantitative Strand
[abbreviated quantitative sections]

## 🗣️ Qualitative Strand
[abbreviated qualitative sections]

## 🔗 Integration & Synthesis
- Points of convergence
- Points of divergence
- Meta-inferences

=== ALWAYS INCLUDE (all modes) ===

## 🚀 Extension Opportunities
- [Specific, actionable extensions]

## 🔗 Knowledge Graph Connections
### Links to Existing Nodes
[Use [[WikiLinks]] for every connection]

### New Atomic Concepts to Create
| Concept | Type | Why New |
|---------|------|---------|

## ❓ Open Research Questions
- [Unresolved questions this paper raises]

---
*Processed by ROS v7.0 · [[{title}]] · {discipline}*"""


# ── Transcript / Voice Script Prompt ──────────────────────────────────────────
TRANSCRIPT_PROMPT = """INPUT TYPE: {input_type}
TASK: Extract atomic knowledge primitives from unstructured spoken content.

Source: {source_name}
Date: {date}
Discipline: {discipline}
Context: {context}

Researcher Profile:
{researcher_profile}

Existing Knowledge Graph:
{existing_nodes}

Raw Transcript:
{content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT: Obsidian note(s). Start with ---

YAML frontmatter:
  title, source, date, discipline, tags, type: transcript/lecture/meeting,
  speakers (if identifiable), key_concepts

## 💡 Key Insights (Atomic)
For each distinct insight:
### Insight: [Concise title]
> [Core claim in 1-2 sentences]
- **Context**: [When/why this was said]
- **Epistemic status**: hypothesis / established / contested / speculative
- **Connects to**: [[concept1]], [[concept2]]
- **Formalization**: $[equation if applicable]$

## 📐 Mathematical / Formal Structures Mentioned
[Extract and formalize any equations, models, or formal claims]

## 🔗 Literature References
[Any papers, authors, theories, or works mentioned → [[WikiLinks]]]

## 🗺️ Concept Map
[Key concepts and their relationships extracted from transcript]

## ❓ Unresolved Questions Raised
- [Questions left open in the discussion]

## 📋 Action Items / Follow-ups
- [ ] [Specific research tasks mentioned]

---
*Processed by ROS v7.0 from {input_type}*"""


# ── Dataset Analysis Prompt ────────────────────────────────────────────────────
DATASET_PROMPT = """INPUT TYPE: Dataset / Data Description
TASK: Infer research design opportunities and data architecture.

Dataset: {dataset_name}
File info: {file_info}
Discipline: {discipline}
Researcher context: {context}

Researcher Profile:
{researcher_profile}

Data Preview / Description:
{content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT: Obsidian note. Start with ---

YAML frontmatter:
  title, type: dataset, discipline, tags, variables_count, obs_count,
  panel_structure, time_coverage, data_source

## 🏗️ Data Architecture
### Structure
- Observation unit: [individual/firm/country/text/image/...]
- Panel: balanced/unbalanced/cross-section, N=?, T=?
- Time coverage: [range]
- Key identifiers: [id vars]

### Variable Taxonomy
| Variable | Type | Role | Notes |
|----------|------|------|-------|

## 🎯 Research Design Opportunities
### Quantitative Designs
- Candidate treatments / outcomes
- Candidate instruments (IV)
- Threshold variables (RDD)
- Cohort structure (DiD)
- Experimental design potential

### Qualitative / Mixed-Method Designs
- Embedded case study potential
- Process tracing variables
- Narrative / textual data present?

## ⚠️ Data Quality Assessment
### Missing Data Patterns
- [Variables, % missing, MAR/MCAR/MNAR]

### Potential Biases
- Selection, attrition, measurement error

### Recommended Controls / Fixed Effects
| Level | Rationale |
|-------|-----------|

## 📊 Descriptive Statistics
[Key summary stats if data provided]

## 🔗 Connects To
[[related papers]], [[methods]], [[datasets]]

## 🚀 Suggested Analyses
- [ ] [Specific analysis with estimator/method]

---
*Processed by ROS v7.0 · Dataset: {dataset_name}*"""


# ── Qualitative / Discourse Analysis Prompt ───────────────────────────────────
QUALITATIVE_PROMPT = """INPUT TYPE: Qualitative Material
MATERIAL TYPE: {material_type}
TASK: Extract first-class semantic entities from qualitative/interpretive content.

Source: {source_name}
Discipline: {discipline}
Theoretical Framework: {framework}
Researcher context: {context}

Researcher Profile:
{researcher_profile}

Existing Knowledge Graph:
{existing_nodes}

Content:
{content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT: Obsidian note. Start with ---

YAML frontmatter:
  title, type: qualitative_analysis, material_type, discipline,
  framework, tags, epistemic_mode: qualitative

## 🔍 Theoretical Framework Applied
- Paradigm: [[Interpretivism]] / [[Constructivism]] / [[Critical Theory]] / [[Phenomenology]] / other
- Key concepts operationalized: [[concept1]], [[concept2]]
- Ontological assumptions: [realist/relativist/critical realist]

## 🗣️ Thematic Analysis
### Theme 1: [Name]
> [Core finding / pattern]
- **Evidence**: [representative quotes/observations]
- **Frequency/Salience**: [how prominent]
- **Connects to**: [[theory]], [[concept]]
- **Tension with**: [[competing interpretation]]

### Theme 2: [Name]
[repeat structure]

## 💬 Discourse / Ideological Analysis
- **Dominant frames**: [how reality is constructed]
- **Silenced voices / absent perspectives**: [what is not said]
- **Power relations embedded**: [who benefits from this framing]
- **Semantic shifts detected**: [how meaning has evolved]

## 🏛️ Institutional / Structural Analysis
- Institutional logics present: [[logic1]], [[logic2]]
- Structural constraints identified
- Agency vs. structure tension

## ⚠️ Reflexivity & Positionality
- Researcher positionality
- Interpretive choices made
- Alternative readings possible

## 🔗 Knowledge Graph Connections
[[theories]], [[authors]], [[concepts]], [[contradictions]]

## ❓ Open Interpretive Questions
- [Unresolved hermeneutic tensions]

---
*Processed by ROS v7.0 · Qualitative Analysis · {discipline}*"""


# ── Equation / Theory Note Prompt ─────────────────────────────────────────────
EQUATION_PROMPT = """INPUT TYPE: Equation / Theory Fragment
DISCIPLINE: {discipline}
TASK: Create atomic mathematical/theoretical knowledge primitive.

Context: {context}
Researcher Profile: {researcher_profile}

Content:
{content}

OUTPUT: Atomic theory note. Start with ---

YAML: title, type: equation, discipline, tags, field, assumptions, epistemic_mode: formal

## 📐 Mathematical / Formal Statement
$$[equation or formal statement]$$

## 🔍 Notation
| Symbol | Meaning | Domain |
|--------|---------|--------|

## 📋 Assumptions Required
- [Each assumption for validity]

## 🔗 Derivation / Intuition
[Key steps or scientific/theoretical intuition]

## 🌐 Connections
[[related estimators/theorems]], [[papers using this]], [[assumptions]], [[discipline-specific applications]]

## ⚠️ Known Violations / Edge Cases
- [When this breaks down]

---"""


# ── General Notes / Ideas Prompt ──────────────────────────────────────────────
NOTES_PROMPT = """INPUT TYPE: Research Notes / Ideas
DISCIPLINE: {discipline}
TASK: Transform raw intellectual content into atomic Obsidian primitives.

Context: {context}
Researcher Profile: {researcher_profile}
Existing Graph: {existing_nodes}

Content:
{content}

OUTPUT: Atomic note(s). Start with ---

YAML: title, type: notes, discipline, tags, epistemic_status: fleeting/literature/permanent

## 💡 Core Insight
> [1-2 sentence crystallization]

## 🔗 Theoretical Lineage
- Builds on: [[concept/author]]
- Challenges: [[concept/author]]
- Synthesizes: [[A]] + [[B]]

## 📐 Formalization (if applicable)
$$[equation]$$

## 🌐 Knowledge Graph Connections
[[concepts]], [[papers]], [[methods]]

## ❓ Open Questions
- [What remains unresolved]

## 📋 Next Steps
- [ ] [Concrete research action]

---
*Processed by ROS v7.0 · {discipline}*"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _call_llm(
    client: OpenAI,
    model: str,
    provider: str,
    messages: list,
    max_tok: int,
    callback: Optional[Callable] = None,
) -> str:
    """스트리밍 → 비스트리밍 폴백 LLM 호출."""
    extra = {"enable_thinking": False} if _is_qwen3(provider, model) else {}
    chunks = []

    try:
        stream = client.chat.completions.create(
            model=model, messages=messages,
            temperature=0.15, max_tokens=max_tok,
            stream=True, **({"extra_body": extra} if extra else {}),
        )
        for chunk in stream:
            t = _extract_text(chunk)
            if t:
                chunks.append(t)
                if callback: callback(t)
        if chunks:
            return "".join(chunks)
    except Exception:
        pass  # 스트리밍 실패 → 폴백

    resp = client.chat.completions.create(
        model=model, messages=messages,
        temperature=0.15, max_tokens=max_tok,
        stream=False, **({"extra_body": extra} if extra else {}),
    )
    result = resp.choices[0].message.content or ""
    if callback: callback(result)
    return result


def _format_profile(profile: dict) -> str:
    if not profile:
        return "No profile set."
    lines = []
    if profile.get("name"):        lines.append(f"Researcher: {profile['name']}")
    if profile.get("discipline"):  lines.append(f"Primary Discipline: {profile['discipline']}")
    if profile.get("interests"):   lines.append(f"Research Interests: {', '.join(profile['interests'])}")
    if profile.get("methods"):     lines.append(f"Preferred Methods: {', '.join(profile['methods'])}")
    if profile.get("projects"):    lines.append(f"Active Projects: {', '.join(profile['projects'])}")
    if profile.get("questions"):   lines.append(f"Open Questions: {'; '.join(profile['questions'][:3])}")
    return "\n".join(lines) if lines else "No profile set."


def _detect_epistemic_mode(content: str, discipline: str) -> str:
    """입력 내용과 학문 분야로부터 에피스테믹 모드를 자동 감지."""
    content_lower = content.lower()
    disc_lower = discipline.lower()

    # 질적 지표
    qual_signals = ["interview", "ethnograph", "discourse", "thematic", "grounded theory",
                    "narrative", "qualitative", "interpretiv", "phenomenolog", "case study",
                    "participant observation", "field note", "coding", "saturation"]
    # 양적 지표
    quant_signals = ["regression", "estimat", "coefficient", "p-value", "standard error",
                     "ols", "iv", "did", "rdd", "rct", "bayesian", "maximum likelihood",
                     "causal", "treatment effect", "identification", "instrument"]

    qual_score  = sum(1 for s in qual_signals  if s in content_lower)
    quant_score = sum(1 for s in quant_signals if s in content_lower)

    # 학문 분야 기반 기본값
    qual_disciplines  = {"sociology", "anthropology", "communicationstudies", "history",
                         "philosophy", "linguistics", "literature", "arthistory"}
    quant_disciplines = {"economics", "econometrics", "statistics", "physics", "chemistry",
                         "biology", "medicine", "epidemiology", "machineLearning"}

    disc_norm = disc_lower.replace(" ", "").replace("_", "")
    if disc_norm in qual_disciplines and qual_score >= quant_score:
        return "qualitative"
    if disc_norm in quant_disciplines and quant_score > qual_score:
        return "quantitative"

    if qual_score > 0 and quant_score > 0:
        return "mixed"
    if qual_score > quant_score:
        return "qualitative"
    if quant_score > qual_score:
        return "quantitative"
    return "quantitative"  # 기본값


def analyze_paper(
    api_key: str, base_url: str, model: str,
    title: str, authors: str, year: str, journal: str, zotero: str,
    existing_nodes: list, researcher_profile: dict,
    content: str,
    discipline: str = "General",
    epistemic_mode: str = "auto",
    callback: Optional[Callable] = None,
) -> str:
    provider = _detect_provider(base_url, model)
    client   = _build_client(api_key, base_url)
    nodes_str = "\n".join(f"- [[{n}]]" for n in existing_nodes) if existing_nodes else "- (empty graph)"
    profile_str = _format_profile(researcher_profile)

    if epistemic_mode == "auto":
        epistemic_mode = _detect_epistemic_mode(content, discipline)

    prompt = PAPER_PROMPT.format(
        title=title, authors=authors, year=year,
        journal=journal or "Unknown", zotero=zotero or "N/A",
        discipline=discipline, epistemic_mode=epistemic_mode,
        existing_nodes=nodes_str, researcher_profile=profile_str,
        content=content[:65000],
    )
    msgs = [
        {"role": "system", "content": ROS_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    if callback: callback(f"[ROS v7.0] Paper analysis → {model} | {discipline} | {epistemic_mode}\n")
    return _call_llm(client, model, provider, msgs, _max_tokens(provider), callback)


def validate_api(api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    """Validate the configured OpenAI-compatible chat endpoint."""
    if not api_key:
        return False, "API key is required"
    if not model:
        return False, "Model is required"

    provider = _detect_provider(base_url, model)
    try:
        extra = {"enable_thinking": False} if _is_qwen3(provider, model) else {}
        client = _build_client(api_key, base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0,
            max_tokens=5,
            stream=False,
            **({"extra_body": extra} if extra else {}),
        )
        model_name = getattr(response, "model", None) or model
        return True, f"Connection successful [{provider.upper()}]: {model_name}"
    except Exception as e:
        err = str(e)
        lower = err.lower()
        if "401" in err or "unauthorized" in lower or "invalid_api_key" in lower:
            hint = " - check the API key"
        elif "404" in err or "model" in lower:
            hint = " - check the model name"
        elif "timeout" in lower or "connect" in lower:
            hint = " - check the network or base URL"
        else:
            hint = ""
        return False, f"Connection failed [{provider.upper()}]: {err}{hint}"


def _extract_frontmatter_tags(markdown: str) -> list[str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", markdown or "", re.DOTALL)
    if not match:
        return []

    tags = []
    for line in match.group(1).splitlines():
        if not re.match(r"^\s*tags\s*:", line, re.IGNORECASE):
            continue
        raw = line.split(":", 1)[1].strip()
        if raw.startswith("[") and raw.endswith("]"):
            tags.extend(part.strip().strip("'\"") for part in raw[1:-1].split(","))
        elif raw:
            tags.append(raw.strip().strip("'\""))
    return _unique_preserve_order(tags)


def extract_graph_edges(
    api_key: str,
    base_url: str,
    model: str,
    markdown: str,
    callback: Optional[Callable] = None,
) -> dict:
    """
    Extract graph edges from generated Markdown without another LLM call.

    The worker only needs a stable contract for memory.update_graph(): explicit
    WikiLinks, implicit concept candidates, and note tags. Keeping this
    deterministic avoids a second network dependency after analysis succeeds.
    """
    explicit_links = _unique_preserve_order([
        link.split("|", 1)[0].split("#", 1)[0]
        for link in re.findall(r"\[\[([^\]]+)\]\]", markdown or "")
    ])
    frontmatter_tags = _extract_frontmatter_tags(markdown or "")
    hashtag_tags = re.findall(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]*)", markdown or "")
    tags = _unique_preserve_order(frontmatter_tags + hashtag_tags)

    headings = [
        re.sub(r"\[\[|\]\]", "", h).strip()
        for h in re.findall(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", markdown or "", re.MULTILINE)
    ]
    implicit_links = _unique_preserve_order([
        value for value in tags + headings if value not in explicit_links
    ])

    if callback:
        callback(f"[ROS graph] {len(explicit_links)} explicit links, {len(implicit_links)} implicit links\n")

    return {
        "explicit_links": explicit_links,
        "implicit_links": implicit_links,
        "tags": tags,
    }


def analyze_transcript(
    api_key: str, base_url: str, model: str,
    source_name: str, input_type: str, date: str, context: str,
    existing_nodes: list, researcher_profile: dict,
    content: str,
    discipline: str = "General",
    callback: Optional[Callable] = None,
) -> str:
    provider = _detect_provider(base_url, model)
    client   = _build_client(api_key, base_url)
    nodes_str = "\n".join(f"- [[{n}]]" for n in existing_nodes) if existing_nodes else "- (empty graph)"
    profile_str = _format_profile(researcher_profile)

    prompt = TRANSCRIPT_PROMPT.format(
        source_name=source_name, input_type=input_type,
        date=date, context=context, discipline=discipline,
        existing_nodes=nodes_str, researcher_profile=profile_str,
        content=content[:60000],
    )
    msgs = [
        {"role": "system", "content": ROS_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    if callback: callback(f"[ROS v7.0] Transcript analysis → {model} | {discipline}\n")
    return _call_llm(client, model, provider, msgs, _max_tokens(provider), callback)


def analyze_dataset(
    api_key: str, base_url: str, model: str,
    dataset_name: str, file_info: str, context: str,
    existing_nodes: list, researcher_profile: dict,
    content: str,
    discipline: str = "General",
    callback: Optional[Callable] = None,
) -> str:
    provider = _detect_provider(base_url, model)
    client   = _build_client(api_key, base_url)
    nodes_str = "\n".join(f"- [[{n}]]" for n in existing_nodes) if existing_nodes else "- (empty graph)"
    profile_str = _format_profile(researcher_profile)

    prompt = DATASET_PROMPT.format(
        dataset_name=dataset_name, file_info=file_info,
        context=context, discipline=discipline,
        existing_nodes=nodes_str, researcher_profile=profile_str,
        content=content[:50000],
    )
    msgs = [
        {"role": "system", "content": ROS_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    if callback: callback(f"[ROS v7.0] Dataset analysis → {model} | {discipline}\n")
    return _call_llm(client, model, provider, msgs, _max_tokens(provider), callback)


def analyze_qualitative(
    api_key: str, base_url: str, model: str,
    source_name: str, material_type: str, framework: str, context: str,
    existing_nodes: list, researcher_profile: dict,
    content: str,
    discipline: str = "Sociology",
    callback: Optional[Callable] = None,
) -> str:
    """질적 연구 자료 전용 분석 (인터뷰, 민족지, 담론분석 등)."""
    provider = _detect_provider(base_url, model)
    client   = _build_client(api_key, base_url)
    nodes_str = "\n".join(f"- [[{n}]]" for n in existing_nodes) if existing_nodes else "- (empty graph)"
    profile_str = _format_profile(researcher_profile)

    prompt = QUALITATIVE_PROMPT.format(
        source_name=source_name, material_type=material_type,
        framework=framework, context=context, discipline=discipline,
        existing_nodes=nodes_str, researcher_profile=profile_str,
        content=content[:60000],
    )
    msgs = [
        {"role": "system", "content": ROS_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    if callback: callback(f"[ROS v7.0] Qualitative analysis → {model} | {discipline} | {material_type}\n")
    return _call_llm(client, model, provider, msgs, _max_tokens(provider), callback)


def analyze_equation(
    api_key: str, base_url: str, model: str,
    context: str, researcher_profile: dict,
    content: str,
    discipline: str = "Mathematics",
    callback: Optional[Callable] = None,
) -> str:
    provider = _detect_provider(base_url, model)
    client   = _build_client(api_key, base_url)
    profile_str = _format_profile(researcher_profile)

    prompt = EQUATION_PROMPT.format(
        context=context, discipline=discipline,
        researcher_profile=profile_str,
        content=content[:20000],
    )
    msgs = [
        {"role": "system", "content": ROS_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    if callback: callback(f"[ROS v7.0] Equation analysis → {model} | {discipline}\n")
    return _call_llm(client, model, provider, msgs, _max_tokens(provider), callback)


def analyze_notes(
    api_key: str, base_url: str, model: str,
    context: str, existing_nodes: list, researcher_profile: dict,
    content: str,
    discipline: str = "General",
    callback: Optional[Callable] = None,
) -> str:
    provider = _detect_provider(base_url, model)
    client   = _build_client(api_key, base_url)
    nodes_str = "\n".join(f"- [[{n}]]" for n in existing_nodes) if existing_nodes else "- (empty graph)"
    profile_str = _format_profile(researcher_profile)

    prompt = NOTES_PROMPT.format(
        context=context, discipline=discipline,
        existing_nodes=nodes_str, researcher_profile=profile_str,
        content=content[:50000],
    )
    msgs = [
        {"role": "system", "content": ROS_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    if callback: callback(f"[ROS v7.0] Notes analysis → {model} | {discipline}\n")
    return _call_llm(client, model, provider, msgs, _max_tokens(provider), callback)
