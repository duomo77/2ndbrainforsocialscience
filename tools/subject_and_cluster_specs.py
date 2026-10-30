# -*- coding: utf-8 -*-
"""
subject_and_cluster_specs.py
============================
Creates Subject Maps of Content (MOCs), Research Clusters, and Essential Methodology Notes:
1. 8 Subject MOC Notes in Concepts/ (Econometrics, IndustrialOrganization, MachineLearning,
   ExperimentalEconomics, LaborEconomics, PublicEconomics, MarketDesign, GeneralEconomics).
2. 9 Research Cluster Taxonomy Notes in Contexts/ (empirical_and_conduct, mechanism_identification, etc.).
3. 4 Essential Methodology Concept Notes in Concepts/ (Field Experiments, RCT, Conduct Parameter Identification,
   Computational Optimal Transport).
"""

from pathlib import Path


SUBJECT_MOCS = [
    {
        "filename": "Econometrics.md",
        "title": "Econometrics (계량경제학 Master Map of Content)",
        "discipline": "Econometrics",
        "aliases": ["Econometrics", "계량경제학"],
        "overview": "인과추론(Causal Inference), 준실험 설계(Quasi-Experimental Design), 이중머신러닝(DML), 고차원 패널 분석 및 베이지안 계량경제학의 통합 MOC.",
        "core_pillars": [
            "**잠재결과 및 매칭**: Rosenbaum & Rubin (1983), Abadie & Imbens (2006, 2016), Iacus et al. (2012 CEM), Hainmueller (2012 Entropy Balancing)",
            "**회귀단절설계 (RDD)**: McCrary (2008), Calonico et al. (2014, 2020 CER), Armstrong & Kolesár (2018, 2020 Minimax Honest Bandwidth), Cattaneo et al. (2015 Local Randomization)",
            "**이중차분 및 패널 (DiD & Panel)**: Card & Krueger (1994), Bertrand et al. (2004), Callaway & Sant'Anna (2021), Sun & Abraham (2021), Arkhangelsky et al. (2021 SDID), Athey et al. (2021 Matrix Completion), Imai & Kim (2021)",
            "**도구변수 (IV)**: Angrist & Imbens (1994 LATE), Card (1995 College Proximity), Bound et al. (1995 Weak IV), Goldsmith-Pinkham et al. (2020 Bartik)",
            "**이중머신러닝 (DML)**: Chernozhukov et al. (2018 Neyman Orthogonality), Wager & Athey (2018 Causal Forest), Athey & Wager (2021 Policy Learning)",
            "**베이지안 계량경제학**: Rubin (1978), Ibrahim & Chen (2000 Power Prior), Park et al. (2004 MrP), Gelman (2006 Priors), Hobbs et al. (2011 Commensurate Prior), Ghitza & Gelman (2013 Deep MrP), Hahn et al. (2020 Bayesian Causal Forests)"
        ]
    },
    {
        "filename": "IndustrialOrganization.md",
        "title": "Industrial Organization (산업조직론 Master Map of Content)",
        "discipline": "IndustrialOrganization",
        "aliases": ["IndustrialOrganization", "산업조직론"],
        "overview": "실증 산업조직론(Empirical IO), BLP 수요·공급 구조추정, 기업 결합 및 암묵적 담합 검정, 생산함수 식별, 알고리즘 가격 책정 및 반독점 감사의 통합 MOC.",
        "core_pillars": [
            "**수요 및 시장지배력 구조추정**: Berry, Levinsohn & Pakes (1995 BLP), Nevo (2001 Cereal), Dubé et al. (2012 MPEC), Conlon & Gortmaker (2020 PyBLP)",
            "**과점 공급 및 담합 판정**: Bresnahan (1982), Porter (1983 JEC), Green & Porter (1984), Miller & Weinberg (2017 MillerCoors Collusion Testing), Backus et al. (2021 Common Ownership)",
            "**생산함수 식별**: Olley & Pakes (1996), Levinsohn & Petrin (2003), Ackerberg, Caves & Frazer (2015 ACF), Gandhi, Navarro & Rivers (2020 Gross Output FOC)",
            "**알고리즘 가격 담합 & 반독점 감사**: Calvano et al. (2020, 2021, 2023), Asker et al. (2024), Moraes et al. (2026), Nisan & Zerah (2026), Kim (2026 Beyond High Prices Audit)"
        ]
    },
    {
        "filename": "MachineLearning.md",
        "title": "Machine Learning & Reinforcement Learning (기계학습·강화학습 Master Map of Content)",
        "discipline": "MachineLearning",
        "aliases": ["MachineLearning", "머신러닝", "인공지능"],
        "overview": "강화학습(RL), 다중에이전트 강화학습(MARL), 최적수송(Optimal Transport), 생성형 에이전트(Generative Agents) 및 적대적 감사(Adversarial Audit)의 수리적 통합 MOC.",
        "core_pillars": [
            "**심층 강화학습**: Mnih et al. (2015 DQN), Schulman et al. (2017 PPO), Haarnoja et al. (2018 SAC)",
            "**다중에이전트 강화학습 (MARL)**: Foerster et al. (2018 COMA, LOLA), Lowe et al. (2017 MADDPG), Sunehag et al. (2017 VDN), Baek (2025 CCOMA)",
            "**최적수송 및 기하학적 딥러닝**: Cuturi (2013 Sinkhorn), Arjovsky et al. (2017 WGAN), Genevay et al. (2018 Sinkhorn Divergence), Peyré & Cuturi (2019 Computational OT)",
            "**생성형 에이전트 및 사회 시뮬레이션**: Park et al. (2024 Stanford 1,000 People), Google (2024 AI Agents Whitepaper)",
            "**적대적 강건성 및 감사**: Madry et al. (2018 PGD Adversarial Audit)"
        ]
    },
    {
        "filename": "ExperimentalEconomics.md",
        "title": "Experimental Economics & Policy RCTs (실험경제학 및 정책실험 Master Map of Content)",
        "discipline": "ExperimentalEconomics",
        "aliases": ["ExperimentalEconomics", "실험경제학", "정책실험"],
        "overview": "실험실 및 현장 실험(Lab & Field Experiments), 사회적 선호, 간섭 및 파급효과(Interference & Spillovers), 다국가 정책 RCT의 종합 MOC.",
        "core_pillars": [
            "**현장 실험 방법론**: List (2006 Gift Exchange), Levitt & List (2007 Lab vs Field), Duflo et al. (2007 RCT Toolkit), DellaVigna et al. (2012 Door-to-Door)",
            "**사회적 선호 및 인센티브**: Fehr & Schmidt (1999 Inequity Aversion), Gneezy et al. (2011 When Incentives Fail), Charness & Gneezy (2009 Exercise Incentives)",
            "**간섭 및 일반균형 파급효과**: Miguel & Kremer (2004 Worms), Baird et al. (2016, 2018 Spillover Inference), Aronow & Samii (2017 Interference), Egger et al. (2022 General Equilibrium)",
            "**다국가·대규모 정책 RCT**: Banerjee et al. (2015 Science 6-Country Graduation RCT), Banerjee et al. (2015 AEJ Microfinance), Duflo et al. (2011 Tracking)"
        ]
    },
    {
        "filename": "LaborEconomics.md",
        "title": "Labor Economics (노동경제학 Master Map of Content)",
        "discipline": "LaborEconomics",
        "aliases": ["LaborEconomics", "노동경제학", "Papers/LaborEconomics"],
        "overview": "인적자본 및 교육수익률, 공간적 선별 및 어메니티, 성별 임금격차, 육아휴직 및 가구 내 협상, Roy 선택 모형의 종합 MOC.",
        "core_pillars": [
            "**인적자본 및 교육수익률**: Card (1995, 2001 College Proximity IV), Chetty et al. (2011 STAR Experiment)",
            "**공간 선별 및 후생 불평등**: Diamond (2016 AER Spatial Amenities), Moretti (2013 Local Labor Markets)",
            "**성별 격차 및 직장 문화**: Cullen & Perez-Truglia (2023 AER Old Boys' Club), Kleven et al. (2019 Child Penalty), Patnaik (2019 AEJ:Applied Fathers' Quotas)",
            "**기술변화 및 노동수요**: Autor et al. (2003 ALM Task Model), Acemoglu & Restrepo (2018 Automation), Autor et al. (2020 Superstar Firms), Acemoglu et al. (2022 AI and Jobs)",
            "**비교우위 및 선택**: Roy (1951 Earnings Distribution), Heckman (1979 Sample Selection)"
        ]
    },
    {
        "filename": "PublicEconomics.md",
        "title": "Public Economics (재정경제학 Master Map of Content)",
        "discipline": "PublicEconomics",
        "aliases": ["PublicEconomics", "재정경제학"],
        "overview": "최적 조세 이론, 공공 지출의 한계후생가치(MVPF), 현금 지원 및 바우처 복지, 영아·아동수당 정책평가 및 관료제 정치경제학의 종합 MOC.",
        "core_pillars": [
            "**최적 조세 및 노동공급**: Saez (2001 AER Optimal Income Taxation), Chetty et al. (2009 Salience and Taxation), Chetty et al. (2013 EITC Knowledge)",
            "**공공지출 복지 평가 (MVPF)**: Hendren & Sprung-Keyser (2020 QJE A Unified Welfare Analysis of 133 Programs)",
            "**보건 및 사회안전망**: Finkelstein et al. (2012 Oregon Health Insurance Experiment), Hoynes et al. (2015 EITC Infant Health), Kline & Walters (2016 Head Start)",
            "**초저출생 및 현금지원 정책**: Kim (2025 Infant Allowance DML-DiD), Kim (2025 Sparse Fertility Bayesian Borrowing)",
            "**관료제 및 정부 역량**: Bertrand et al. (2020 Bureaucrats in India), Geys et al. (2024 APSR Bureaucratic Survival)"
        ]
    },
    {
        "filename": "MarketDesign.md",
        "title": "Market Design & Mechanism Matching (시장설계 Master Map of Content)",
        "discipline": "MarketDesign",
        "aliases": ["MarketDesign", "시장설계", "매칭이론"],
        "overview": "양측 매칭(Two-Sided Matching), 학교 배정(School Choice), 장기 이식(Kidney Exchange), 고빈도 매매 및 배치 경매(Batch Auctions), 경매 설계의 종합 MOC.",
        "core_pillars": [
            "**양측 매칭 기초**: Gale & Shapley (1962 College Admissions), Roth & Sotomayor (1990 Two-Sided Matching)",
            "**학교 배정 및 형평성**: Abdulkadiroğlu & Sönmez (2003 School Choice), Pathak & Sönmez (2008 AER Boston Leveling Playing Field)",
            "**장기 이식**: Roth, Sönmez & Ünver (2004 QJE Kidney Exchange)",
            "**금융시장 및 경매 설계**: Budish, Cramton & Shim (2015 QJE Frequent Batch Auctions), Milgrom (2000 Spectrum Auctions)"
        ]
    },
    {
        "filename": "GeneralEconomics.md",
        "title": "General Economics & Game Theory (경제학 원론 및 게임이론 Master Map of Content)",
        "discipline": "GeneralEconomics",
        "aliases": ["GeneralEconomics", "경제학원론", "일반경제학"],
        "overview": "미시경제 이론, 게임이론(반복 게임 및 민속정리), 불완전 관측 하의 균형, 거시 에이전트 동역학의 종합 MOC.",
        "core_pillars": [
            "**게임이론 및 민속정리**: Fudenberg & Maskin (1986), Abreu, Pearce & Stacchetti (1986, 1990 APS), Fudenberg, Levine & Maskin (1994 FLM)",
            "**일반균형 및 후생경제학**: Arrow & Debreu (1954), Mas-Colell, Whinston & Green (1995 Microeconomic Theory)",
            "**정보경제학 및 계약이론**: Stiglitz & Weiss (1981 Credit Rationing), Holmström (1979 Moral Hazard)"
        ]
    }
]


RESEARCH_CLUSTERS = [
    {
        "filename": "empirical_and_conduct.md",
        "title": "Research Cluster: Empirical IO & Conduct Parameter Estimation",
        "aliases": ["empirical_and_conduct", "실증IO_행태모수"],
        "body": "Bresnahan (1982), Porter (1983), Miller & Weinberg (2017 Econometrica), Backus et al. (2021 AER)으로 이어지는 시장 지배력 및 정태적 Conduct Parameter ($\theta$) 식별 문헌 클러스터."
    },
    {
        "filename": "mechanism_identification.md",
        "title": "Research Cluster: Mechanism Identification & Dynamic Auditing",
        "aliases": ["mechanism_identification", "메커니즘식별"],
        "body": "단순 초과가격 관측을 넘어 반사실적 정책 개입(Do-Intervention)과 이탈 보복 손실 분해를 통해 동태적 유인양립성(DIC)을 검증하는 감사 메커니즘 식별 클러스터 (Kim 2026, Asker 2024, Moraes 2026)."
    },
    {
        "filename": "learning_design.md",
        "title": "Research Cluster: Algorithmic Learning Design & Exploration Dynamics",
        "aliases": ["learning_design", "학습설계동역학"],
        "body": "Q-Learning, PPO, MADDPG, VDN 등 강화학습 에이전트의 내부 구조, 메모리(GRU), 탐색 노이즈 및 동조화(Coupling) 현상을 다루는 문헌 클러스터 (Calvano 2020, Banchio 2022, Brusatin 2024)."
    },
    {
        "filename": "conceptual_boundaries.md",
        "title": "Research Cluster: Conceptual Boundaries — Tacit Collusion vs Conscious Parallelism",
        "aliases": ["conceptual_boundaries", "개념적경계"],
        "body": "독점규제법상 '합의(Agreement)'의 법적 요건과 알고리즘이 학습하는 암묵적 동조화, 그리고 가짜 담합(Spurious Collusion)과 진짜 담합(Genuine Collusion)의 개념적 경계를 탐색하는 클러스터."
    },
    {
        "filename": "screens_and_model_tests.md",
        "title": "Research Cluster: Structural Screens & Collusion Model Tests",
        "aliases": ["screens_and_model_tests", "구조적스크린"],
        "body": "가격 분산 급감(Harrington 2005, 2006), 마코프 정권 전환(Porter 1983), 입찰 담합 검정(Bajari & Summers 2003) 등 시장 데이터 기반 구조적 스크리닝 클러스터."
    },
    {
        "filename": "algorithmic_foundations.md",
        "title": "Research Cluster: Algorithmic Foundations of Pricing",
        "aliases": ["algorithmic_foundations", "알고리즘기초"],
        "body": "반복 가격 책정 게임에서 강화학습 알고리즘의 수렴 특성, 벨만 잔차 수렴성, 이산 격자 효과를 다루는 알고리즘 기초 클러스터."
    },
    {
        "filename": "repeated_game_theory.md",
        "title": "Research Cluster: Repeated Game Theory & Imperfect Monitoring",
        "aliases": ["repeated_game_theory", "반복게임이론"],
        "body": "Green & Porter (1984), Abreu, Pearce & Stacchetti (1986, 1990), Fudenberg, Levine & Maskin (1994)의 공적 신호 하 반복 죄수의 딜레마 및 민속정리 수리적 기초 클러스터."
    },
    {
        "filename": "regret_auditing.md",
        "title": "Research Cluster: Regret Minimization & Domination-Avoiding Auditing",
        "aliases": ["regret_auditing", "후회최소화감사"],
        "body": "외부 후회 최소화(No-external regret), 약한 지배 회피(Domination-avoiding, Nisan & Zerah 2026), 최악 경우 적대적 감사(Madry 2018 PGD)를 결합한 알고리즘 감사 클러스터."
    },
    {
        "filename": "structural_identification.md",
        "title": "Research Cluster: Structural Identification in Econometrics & IO",
        "aliases": ["structural_identification", "구조적식별"],
        "body": "BLP 수요 체계(Berry 1994, BLP 1995), 생산함수 1계조건 식별(Gandhi, Navarro & Rivers 2020), Neyman 직교화 DML(Chernozhukov 2018)을 통합하는 현대 계량 식별 클러스터."
    }
]


METHODOLOGY_CONCEPTS = [
    {
        "filename": "Field Experiments.md",
        "title": "Field Experiments (현장 실험)",
        "aliases": ["Field Experiments", "현장실험", "Natural Field Experiments"],
        "category": "ExperimentalEconomics",
        "def_ko": "경제 주체들이 실험 환경임을 인식하지 못하거나(Natural Field Experiment) 실제 시장 과업을 수행하는 자연스러운 환경에서 무작위 배정을 실행하여 내적 타당성과 외적 타당성을 동시에 확보하는 실험 설계.",
        "formula": r"\tau_{FE} = \mathbb{E}[Y_i(1) \mid \text{Natural Context}] - \mathbb{E}[Y_i(0) \mid \text{Natural Context}]",
        "distinction": "실험실 실험(Lab)의 인위적 관찰자 편향(Hawthorne Effect)을 극복하고 실제 시장 균형 반응을 관측할 수 있음 (Levitt & List 2007, List 2006).",
        "links": ["[[Randomized Controlled Trials (RCT)]]", "[[2006_List_The Behavioralist Meets the Market_ A Dual Approach to Sorting and Learning with Professional Market Vendors]]", "[[2007_Levitt_What Do Laboratory Experiments Measuring Social Preferences Reveal About the Real World_]]"]
    },
    {
        "filename": "Randomized Controlled Trials (RCT).md",
        "title": "Randomized Controlled Trials (RCT, 무작위 통제 시험)",
        "aliases": ["Randomized Controlled Trials (RCT)", "무작위통제시험", "RCT"],
        "category": "Econometrics",
        "def_ko": r"처치 배정 $D_i$를 완벽히 무작위화하여 잠재결과와 처치 배정 간의 통계적 독립성($(Y_i(1), Y_i(0)) \perp D_i$)을 달성함으로써 모든 관측 및 비관측 교란변수를 완벽히 통제하는 인과추론의 황금 표준(Gold Standard).",
        "formula": r"\mathbb{E}[Y \mid D=1] - \mathbb{E}[Y \mid D=0] = \mathbb{E}[Y(1) - Y(0)] = \text{ATE}",
        "distinction": "인과적 편향은 0이나, 표본 간 간섭(SUTVA 위배) 및 일반균형 파급효과가 존재할 경우 단순 ATE는 전체 경제 효과를 과소/과대평가할 수 있음 (Miguel & Kremer 2004, Banerjee et al. 2015 Science).",
        "links": ["[[Field Experiments]]", "[[2004_Miguel_Worms_ Identifying Impacts on Education and Health in the Presence of Treatment Externalities]]", "[[2015_Banerjee_A Multifaceted Program Causes Sustained Increases in the Wealth of the Very Poor]]"]
    },
    {
        "filename": "Conduct Parameter Identification.md",
        "title": "Conduct Parameter Identification (행태 모수 식별 이론)",
        "aliases": ["Conduct Parameter Identification", "행태모수식별"],
        "category": "IndustrialOrganization",
        "def_ko": "기업의 한계비용을 직접 관측할 수 없을 때, 수요 함수의 회전(Rotation)을 유발하는 외생적 도구변수 $Z$를 활용하여 1계 조건(FOC)에서 마크업 파라미터 $\theta$를 일관되게 분리 추정하는 계량경제학적 식별 이론.",
        "formula": r"P(Q, Z) + \theta_i \cdot \frac{\partial P(Q, Z)}{\partial Q} \cdot q_i = MC_i(q_i) \iff \text{Identified iff } \frac{\partial^2 P}{\partial Q \partial Z} \ne 0",
        "distinction": "Bresnahan (1982)과 Lau (1982)가 확립한 정리로, 단순 수요 곡선의 평행 이동(Shifter)만으로는 한계비용 곡선의 기울기와 행태 모수를 분리 식별할 수 없음.",
        "links": ["[[Conduct Parameter]]", "[[1982_Bresnahan_The Oligopoly Solution Concept Is Identified]]", "[[1982_Lau_On Identifying the Degree of Competitiveness from Industry Price and Output Data]]"]
    },
    {
        "filename": "Computational Optimal Transport.md",
        "title": "Computational Optimal Transport (계산 최적수송)",
        "aliases": ["Computational Optimal Transport", "계산최적수송", "Optimal Transport in Econometrics & Statistics"],
        "category": "MachineLearning",
        "def_ko": "몽주-칸토로비치 최적수송 문제를 엔트로피 정규화(Entropic Regularization)를 통해 싱크혼-크놉(Sinkhorn-Knopp) 양측 행렬 스케일링으로 변환하여 $O(d^2)$의 선형에 가까운 시간 복잡도로 확률분포 간 거리를 계산하는 계산 통계학 기법.",
        "formula": r"W_{c, \varepsilon}(P, Q) = \min_{T \in \Pi(P, Q)} \int c(x, y) \, d T(x, y) + \varepsilon \text{KL}(T \mid P \otimes Q) = \max_{u, v} \langle u, P \rangle + \langle v, Q \rangle - \varepsilon \sum e^{(u_i + v_j - c_{ij})/\varepsilon}",
        "distinction": "Cuturi (2013)와 Peyré & Cuturi (2019)에 의해 확립되었으며, 고차원 분포 인과추론, 분포 강건 최적화(DRO), WGAN의 핵심 계산 엔진으로 활용됨.",
        "links": ["[[Optimal Transport in Econometrics & Statistics]]", "[[2013_Cuturi_Sinkhorn Distances_ Lightspeed Computation of Optimal Transport]]", "[[2019_Peyré_Computational Optimal Transport_ With Applications to Data Science]]"]
    }
]


def build_subject_mocs(vault_dir: Path):
    concepts_dir = vault_dir / "Concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for item in SUBJECT_MOCS:
        filepath = concepts_dir / item["filename"]
        aliases_str = "\n".join(f'  - "{a}"' for a in item["aliases"])
        pillars_str = "\n".join(f"- {p}" for p in item["core_pillars"])

        content = f"""---
title: "{item['title']}"
type: subject_moc
discipline: "{item['discipline']}"
category: "{item['discipline']}"
status: evergreen
tags:
  - subject-moc
  - {item['discipline'].lower()}
  - knowledge-map
aliases:
{aliases_str}
---

# 🗺️ {item['title']}

> **분류**: 학문 분야별 통합 마스터 인덱스 (Disciplinary Map of Content)  
> **총괄 개요**: {item['overview']}

---

## 🏛️ 핵심 기둥 및 대표 문헌 계보 (Core Pillars & Foundational Literature)
{pillars_str}

---

## 🔬 주요 분석 프레임워크 & 방법론
- 본 Vault 내 [[index]] 및 [[_INDEX]]의 해당 주제 노드들과 실시간 양방향 링크 형성.
- 연구 논문 원고 집필 시 본 주제 MOC를 기준으로 문헌 검토(Literature Review) 단락 구성 권장.
"""
        filepath.write_text(content, encoding="utf-8")
        created.append(filepath.name)

    print(f"[*] Created {len(created)} Subject MOC notes in Concepts/")
    return created


def build_research_clusters(vault_dir: Path):
    contexts_dir = vault_dir / "Contexts"
    contexts_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for item in RESEARCH_CLUSTERS:
        filepath = contexts_dir / item["filename"]
        aliases_str = "\n".join(f'  - "{a}"' for a in item["aliases"])

        content = f"""---
title: "{item['title']}"
type: research_cluster
status: active
tags:
  - research-cluster
  - taxonomy
aliases:
{aliases_str}
---

# 🧬 {item['title']}

> **클러스터 성격**: 실증 및 이론 연구 클러스터 (Research Cluster & Methodological Grouping)

---

## 📌 클러스터 정의 및 분석 범위
{item['body']}

---

## 🔗 연계 분석 노드
- [[Methodology Atlas — Collusion Auditing vs Conduct Parameter Estimation]]
- [[Deep Research Context — Auditing Dynamic Incentive Compatibility in Algorithmic Pricing]]
- [[_INDEX]]
"""
        filepath.write_text(content, encoding="utf-8")
        created.append(filepath.name)

    print(f"[*] Created {len(created)} Research Cluster taxonomy notes in Contexts/")
    return created


def build_methodology_concepts(vault_dir: Path):
    concepts_dir = vault_dir / "Concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for item in METHODOLOGY_CONCEPTS:
        filepath = concepts_dir / item["filename"]
        aliases_str = "\n".join(f'  - "{a}"' for a in item["aliases"])
        links_str = "\n".join(f"- {l}" for l in item["links"])

        content = f"""---
title: "{item['title']}"
type: atomic_concept
discipline: "Economics / Methodology"
category: "{item['category']}"
status: evergreen
tags:
  - atomic-concept
  - methodology
aliases:
{aliases_str}
---

# {item['title']}

> **개념 정의**: {item['def_ko']}

---

## 📐 핵심 수식 및 식별 조건 (Mathematical Identification)
$${item['formula']}$$

---

## 💡 연구사적 위치 및 차별점 (Epistemic Distinction)
- {item['distinction']}

---

## 🔗 연계 핵심 노드 (Connected Nodes)
{links_str}
"""
        filepath.write_text(content, encoding="utf-8")
        created.append(filepath.name)

    print(f"[*] Created {len(created)} Methodology Concept notes in Concepts/")
    return created
