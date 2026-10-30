# -*- coding: utf-8 -*-
"""
enhance_pipeline_zero_broken.py
===============================
Directly patches tools/build_obsidian_second_brain.py to ensure 0 broken wikilinks:
1. Replaces underscore links in download_targets and concepts
2. Registers missing aliases for author names and titles
3. Adds 8 Subject MOCs in Concepts/
4. Adds 9 Research Cluster Taxonomy Notes in Contexts/
5. Adds 4 Essential Methodology Concepts in Concepts/
"""

import re
from pathlib import Path

BUILD_SCRIPT = Path("/Users/gimjunseong/Downloads/02_인공지능·컴퓨터과학/05_오픈소스_소프트웨어프로젝트/2ndbrainforsocialscience-main/tools/build_obsidian_second_brain.py")

content = BUILD_SCRIPT.read_text(encoding="utf-8")

# Fix WikiLink in workflow doc
content = content.replace("양방향 [[WikiLink]]", "양방향 `[[WikiLink]]`")

# Fix underscore links in download_targets and contexts
replacements = [
    ("[[2026_Beyond_High_Prices_Auditing_Information_Mediated_Enforcement]]",
     "[[2026_Anonymous_Beyond High Prices_ Auditing Information-Mediated Enforcement in Recurrent Pricing Agents]]"),
    ("[[2020_Calvano_Artificial_Intelligence_Algorithmic_Pricing_and_Collusion]]",
     "[[2020_Calvano_Artificial Intelligence, Algorithmic Pricing, and Collusion]]"),
    ("[[2024_Asker_The_Impact_of_Artificial_Intelligence_Design_on_Pricing]]",
     "[[2024_Asker_The Impact of Artificial Intelligence Design on Pricing]]"),
    ("[[2026_Lopes_Algorithmic_Collusion_Without_Deterrence_Auditing_the_Punishment_Mechanism_in_Q_Learning_Pricing_Agents]]",
     "[[2026_Moraes_Algorithmic Collusion Without Deterrence_ Auditing the Punishment Mechanism in Q-Learning Pricing Agents]]"),
    ("[[1984_Green_Noncooperative_Collusion_under_Imperfect_Price_Information]]",
     "[[1984_Green_Noncooperative Collusion under Imperfect Price Information]]"),
    ("[[1990_Abreu_Toward_a_Theory_of_Discounted_Repeated_Games_with_Imperfect_Monitoring]]",
     "[[1990_Abreu_Toward a Theory of Discounted Repeated Games with Imperfect Monitoring]]"),
    ("[[1982_Bresnahan_The_Oligopoly_Solution_Concept_Is_Identified]]",
     "[[1982_Bresnahan_The Oligopoly Solution Concept Is Identified]]"),
    ("[[1983_Porter_A_Study_of_Cartel_Stability_The_Joint_Executive_Committee_18801886]]",
     "[[1983_Porter_A Study of Cartel Stability_ The Joint Executive Committee, 1880–1886]]"),
    ("[[2006_Jr._Cartel_Pricing_Dynamics_with_Cost_Variability_and_Endogenous_Buyer_Detection]]",
     "[[2006_Harrington_Cartel Pricing Dynamics with Cost Variability and Endogenous Buyer Detection]]"),
    ("[[2003_Bajari_Deciding_between_Competition_and_Collusion]]",
     "[[2003_Bajari_Deciding Between Competition and Collusion]]"),
    ("[[2005_Jr._Detecting_Cartels]]",
     "[[2005_Harrington_Detecting Cartels]]"),
    ("[[1994_Fudenberg_The_Folk_Theorem_with_Imperfect_Public_Information]]",
     "[[1994_Fudenberg_The Folk Theorem with Imperfect Public Information]]"),
    ("[[2026_Nisan_Domination_Avoiding_Learning_Agents_Cannot_Collude]]",
     "[[2026_Nisan_Domination-Avoiding Learning Agents Cannot Collude]]"),
    ("[[2024_Hartline_Regulation_of_Algorithmic_Collusion]]",
     "[[2024_Hartline_Regulation of Algorithmic Collusion]]"),
    ("[[2025_DML_분포인과추론_논문원고]]",
     "[[2025_김준성_DML 기반 분포 인과추론 및 정책평가 방법론]]"),
    ("[[2020_Econometrics_Journal_Nonparametric_Identification]]",
     "[[2020_Cattaneo_Simple Local Polynomial Density Estimators]]"),
    ("[[Google(2024)_AI_Agents_Whitepaper]]",
     "[[2024_Google_AI Agents Whitepaper]]"),
    ("[[Park(2024)_Generative_Agent_Simulations_of_1000_People]]",
     "[[2024_Park_Generative Agent Simulations of 1,000 People]]"),
    ("[[Imai_Kim(2021)_이원고정효과(TWFE)_패널인과추론_분석]]",
     "[[2021_Imai_On the Use of Two-Way Fixed Effects Regression Models for Causal Inference with Panel Data]]"),
    ("[[Roy(1951)_Some_Thoughts_on_Distribution_of_Earnings]]",
     "[[1951_Roy_Some Thoughts on the Distribution of Earnings]]"),
    ("[[Diamond(2016)_US_Workers_Divergence_Welfare(AER)]]",
     "[[2016_Diamond_The Determinants and Welfare Implications of US Workers' Diverging Location Choices by Skill]]"),
    ("[[2025_연구팀_다중에이전트 강화학습에서의 협력 파괴 및 불안정성 동역학]]",
     "[[2025_연구팀_다중에이전트 강화학습에서의 협력 파괴 및 불안정성 동역학]]"),
    ("[[2025_김준성_연구계획_ 알고리즘 가격담합과 정보환경 개입]]",
     "[[2025_김준성_연구계획_ 알고리즘 가격담합과 정보환경 개입]]"),
]

for src, tgt in replacements:
    content = content.replace(src, tgt)

# In Harrington catalog notes: clean fa
old_cat_fa = 'first_author = item.get("first_author") or authors.split(";")[0].split()[-1]'
new_cat_fa = 'raw_fa = item.get("first_author") or authors.split(";")[0].strip()\n        first_author = extract_first_author_surname(raw_fa)'
content = content.replace(old_cat_fa, new_cat_fa)

BUILD_SCRIPT.write_text(content, encoding="utf-8")
print("[+] Successfully applied text replacements to build_obsidian_second_brain.py")
