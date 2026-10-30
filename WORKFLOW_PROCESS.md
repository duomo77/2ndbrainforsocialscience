---
title: "ROS Second Brain — AER 문헌 확보 및 지식 그래프 하네스 구축 프로세스"
date: 2026-10-29
type: workflow_documentation
tags:
  - workflow
  - harness
  - aer-perspective
  - provenance
---

# 🛠️ ROS Second Brain: 문헌 확보 및 지식 그래프 구축 업무 프로세스

본 문서는 [`2ndbrainforsocialscience-main`](/Users/gimjunseong/Downloads/02_인공지능·컴퓨터과학/05_오픈소스_소프트웨어프로젝트/2ndbrainforsocialscience-main) 프로젝트의 **ROS v7.0 인지 아키텍처**를 기반으로, *American Economic Review (AER)* 연구자 및 심사자(Referee)의 관점에서 문헌을 수집·검증·요약하고 옵시디언 세컨드 브레인([`/Users/gimjunseong/Documents/SecondBrain`](/Users/gimjunseong/Documents/SecondBrain))에 지식 그래프로 통합한 전체 엔지니어링 및 학술 프로토콜을 기록합니다.

---

## 1. 학술 윤리 및 저작권 준수 원칙 (Provenance & Compliance Policy)

1. **페이월 우회 도구 미사용 (Strict Copyright & Access Control Compliance)**:
   - 요청된 `Sci-Hub-MCP-Server` 등 비공식 페이월 우회(Shadow Library) 경로는 연구 윤리 및 보안/접근제어 가이드라인(`No subscription or authentication restrictions bypassed`)에 따라 사용하지 않았습니다.
2. **공식 DOI 메타데이터 + 적법한 오픈액세스(Open Access) 리포지토리 활용**:
   - **Crossref / OpenAlex API**: 모든 필수 문헌의 정확한 DOI, 저자, 출판 연도, 저널 권호 및 오픈액세스 판본 위치를 검증했습니다.
   - **NBER Working Papers / arXiv / 저자 공개 아카이브**: 저작권 문제가 없는 공식 공개 판본(NBER WP 1409, 4470, 6192, 7853 및 arXiv:1608.00060 등)의 원문 PDF를 직접 다운로드하고 SHA-256 해시 및 전체 텍스트(`text/*.txt`)를 추출했습니다.
   - **판본 분리 원칙**: 출판본(Version of Record)과 작업논문(Working Paper)의 연도나 수치가 다를 수 있음을 각 노트의 프론트매터(`evidence_status`, `downloaded_version`)에 명시했습니다.

---

## 2. 엔드투엔드 파이프라인 아키텍처 (Harness Workflow)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    1. 문헌 소스 및 DOI 식별 계층                        │
│  • 기존 문헌 라이브러리 (/Users/gimjunseong/Documents/paper/literature) │
│  • 로컬 연구 원고 및 다운로드 논문 (/Users/gimjunseong/Downloads)       │
│  • AER 필수 고전 및 방법론 논문 (DOI 검증 + NBER/arXiv OA PDF 확보)     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    2. 텍스트 추출 및 메타데이터 정규화                  │
│  • PyMuPDF (fitz) 기반 전문 텍스트 추출 (literature/text/*.txt)         │
│  • catalog.json & literature_review_ko.md의 비판적 검토 매핑            │
│  • SHA-256 무결성 검증 및 출처(Provenance) 태깅                         │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 3. ROS v7.0 지식 원자(Knowledge Primitive) 변환         │
│  • YAML Frontmatter 생성 (discipline, epistemic_mode, doi, tags)        │
│  • 🎯 연구 질문 & 한계적 기여 (Marginal Contribution)                   │
│  • 🔗 인과/통계 아키텍처 & 지배 방정식 (LaTeX 수식 정식화)              │
│  • 🏛️ AER Researcher Critique (본 연구와의 식별론적 연결고리)          │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               4. 옵시디언 세컨드 브레인 그래프 동기화                   │
│  • 볼트 경로: /Users/gimjunseong/Documents/SecondBrain                  │
│  • 주제별 자동 분류 (IndustrialOrganization, Econometrics 등 6개 분과)  │
│  • 17개 핵심 개념 노트(Concepts/) 및 방법론 아틀라스 양방향 ```` │
│  • 루트 색인 (_INDEX.md) 자동 빌드 및 통계 집계                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. AER 연구자 관점에서 추가 구축된 7대 필수 기반 논문 (Foundational Pillars)

기존 40편의 알고리즘 담합 문헌과 16편의 로컬 연구 논문을 학술적으로 단단히 결속시키기 위해, **AER / Econometrica / JPE / RAND**의 7대 핵심 고전 및 방법론 논문을 추가 확보·연결했습니다:

| ID | 논문 (저자, 연도, 출처) | DOI | 확보 판본 | 본 연구(Beyond High Prices)와의 핵심 연결고리 |
|---|---|---|---|---|
| `stigler1964` | **Stigler (1964)** *A Theory of Oligopoly*, JPE | `10.1086/258853` | DOI 메타데이터 검증 | 담합 유지를 '은밀한 가격 인하의 통계적 탐지(Detection)' 문제로 정식화한 시조. 가우시안 신호 감사의 이론적 출발점. |
| `rotembergsaloner1986` | **Rotemberg & Saloner (1986)** *Price Wars during Booms*, AER | `10.3386/w1409` | **NBER WP 1409 PDF (65p)** | Green-Porter(불황기 오경보 가격전쟁)의 대척점. 호황기 이탈 유인 증가와 유인양립성(IC) 제약을 분석. Epivent & Lambin (2024) 해석의 핵심 준거. |
| `maskintirole1988` | **Maskin & Tirole (1988)** *A Theory of Dynamic Oligopoly II*, Econometrica | `10.2307/1911701` | DOI 메타데이터 검증 | 1기간 상태 기억과 교대 가격 결정(Alternating-move MPE)만으로 초경쟁 고가격과 Edgeworth 주기가 창발함을 증명. Klein (2021), Conjeaud (2026)의 이론적 모태. |
| `ellison1994` | **Ellison (1994)** *Theories of Cartel Stability and the JEC*, RAND | `10.3386/w4470` | **NBER WP 4470 PDF (36p)** | Porter (1983) 데이터를 동태적 마코프 전환 모형으로 재검정하여 Green-Porter vs Rotemberg-Saloner를 실증 판별한 표준 문헌. |
| `genesovemullin1998` | **Genesove & Mullin (1998)** *Testing Static Oligopoly Models*, RAND | `10.3386/w6192` | **NBER WP 6192 PDF (43p)** | 실제 관측된 한계비용($MC$)으로 Bresnahan (1982)의 구조적 Conduct Parameter($\theta$) 추정치를 직접 검증(Validation). 시뮬레이션 감사 검증 설계의 방법론적 선례. |
| `borenstein2002` | **Borenstein, Bushnell & Wolak (2002)** *Measuring Market Inefficiencies*, AER | `10.1257/000282802762024557` | **NBER WP 7853 PDF (48p)** | 반사실적 경쟁 벤치마크(Counterfactual Competitive Baseline)를 구축하여 비용·희소성 효과와 순수 시장지배력을 분리한 AER 금자탑 논문. |
| `chernozhukov2018` | **Chernozhukov et al. (2018)** *Double/Debiased Machine Learning*, Econometrics J. | `10.1111/ectj.12097` | **arXiv:1608.00060 PDF (71p)** | 네이만 직교화(Neyman Orthogonality)와 교차적합을 통한 고차원 인과추론의 표준. 볼트 내 DML-DiD 및 분포 인과추론 연구의 핵심 기반. |

---

## 4. AER 심사자 관점의 4대 핵심 연결고리 (Intellectual Synthesis)

볼트 내 [`Deep Research Context`](/Users/gimjunseong/Documents/SecondBrain/Contexts/Deep%20Research%20Context%20—%20Auditing%20Dynamic%20Incentive%20Compatibility%20in%20Algorithmic%20Pricing.md)와 각 논문 노트에 다음 4가지 핵심 학술 연결고리를 심었습니다:

1. **정보-집행 계보 (Information & Enforcement Lineage)**:
   - `[[1964_Stigler_A Theory of Oligopoly]]` $\to$ `[[1984_Green_Noncooperative Collusion under Imperfect Price Information]]` $\to$ `[[1990_Abreu_Toward a Theory of Discounted Repeated Games with Imperfect Monitoring]]` $\to$ `[[2026_Anonymous_Beyond High Prices_ Auditing Information-Mediated Enforcement in Recurrent Pricing Agents]]`
   - *핵심 통찰*: 처벌은 단순한 가격 하락 그래프가 아니라, 잡음 공적 신호 하에서 이탈 이득을 상쇄하는 계속가치(Continuation Value)의 하락 제약이다.
2. **가짜 담합(Spurious) 대 진짜 담합(Genuine)의 식별 경계**:
   - `[[1988_Maskin_A Theory of Dynamic Oligopoly, II_ Price Competition, Kinked Demand Curves, and Edgeworth Cycles]]` & `[[2024_Asker_The Impact of Artificial Intelligence Design on Pricing]]` $\to$ `[[2023_Calvano_Algorithmic Collusion_ Genuine or Spurious_]]` $\to$ `[[2026_Moraes_Algorithmic Collusion Without Deterrence_ Auditing the Punishment Mechanism in Q-Learning Pricing Agents]]`
   - *핵심 통찰*: 0 할인율($\delta=0$), 반사실적 갱신(Counterfactual updating), 불완전 탐색만으로도 고가격이 발생할 수 있으므로, 반드시 **음성 대조군(Negative Control)을 갖춘 반사실적 정책 개입(Do-intervention)**이 요구된다.
3. **수요 충격과 가격 전쟁 방향성의 비식별성 해소**:
   - `[[1984_Green_Noncooperative Collusion under Imperfect Price Information]]` vs `[[1986_Rotemberg_A Supergame-Theoretic Model of Price Wars during Booms]]` $\to$ `[[1994_Ellison_Theories of Cartel Stability and the Joint Executive Committee, 1880-1886]]` $\to$ `[[2024_Epivent_On Algorithmic Collusion and Reward–Punishment Schemes]]`
   - *핵심 통찰*: 가격 전쟁이 불황기에 터지는지 호황기에 터지는지만으로 담합 여부를 판정할 수 없으며, 정책 함수에 대한 직접 질의를 통해 이탈 유인 제약(DIC)을 직접 계산해야 한다.
4. **구조적 마크업 검증(Validation)에서 알고리즘 감사 검증으로의 방법론 전이**:
   - `[[1982_Bresnahan_The Oligopoly Solution Concept Is Identified]]` & `[[1982_Lau_On Identifying the Degree of Competitiveness from Industry Price and Output Data]]` $\to$ `[[1998_Genesove_Testing Static Oligopoly Models_ Conduct and Cost in the Sugar Industry, 1890-1914]]` & `[[2002_Borenstein_Measuring Market Inefficiencies in California's Restructured Wholesale Electricity Market]]` $\to$ `[[2022_Igami_Measuring the Incentive to Collude_ The Vitamin Cartels, 1990–99]]`
   - *핵심 통찰*: 정태적 마크업($\theta$) 식별과 동태적 유인양립성(DIC) 감사는 상호 보완적이며, 알려진 구조 모형 하에서 감사 지표를 검증(Audit Validation with Proved Negative Controls)하는 것이 현대 경제학 설득의 핵심이다.

---

## 5. 재현 및 실행 명령어 (Reproducibility)

하네스 스크립트는 언제든 반복 실행(Idempotent execution) 가능하며, 새로운 PDF나 카탈로그 항목 추가 시 볼트 전체와 `_INDEX.md`를 자동으로 재구축합니다:

```bash
python3 "/Users/gimjunseong/Downloads/02_인공지능·컴퓨터과학/05_오픈소스_소프트웨어프로젝트/2ndbrainforsocialscience-main/tools/build_obsidian_second_brain.py"
```
