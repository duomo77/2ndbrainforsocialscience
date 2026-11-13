# Instrumental-variable feasibility audit

## Decision

**Do not run 2SLS with the retrieved dataset.** There is no validated municipality-level instrument Z in the analysis files. First-stage coefficients, partial R², F statistics, weak-IV tests and 2SLS coefficients are therefore unavailable, not zero. The correlations and OLS estimates are descriptive. A 2015 population share is not automatically a valid instrument for the 2024 share.

## Candidate comparison

| Candidate | Data needed | Relevance assessment | Main exclusion concern | Current decision |
| --- | --- | --- | --- | --- |
| Historical refugee dispersal | Actual initial administrative placements by municipality, year and origin, preferably 1987–1991; baseline population; historical boundary mapping; placement rules and officer-observed characteristics | Persistence into 2015/2024 populations must be measured, not assumed. Secondary migration and metro-only restriction may weaken it considerably. | Housing supply, local labor demand and long-lived welfare infrastructure can influence current investigation duration independently of the chosen population share. | Feasibility only. No authenticated placement microdata or harmonized municipal Z. |
| Immigration shift-share | Pre-period municipal stocks by origin, national origin-specific inflows or externally motivated shocks, denominators, comparable geography and years | Needs a first stage after the identical controls/FE used in the outcome model. Aggregate foreign-born shares alone cannot construct origin-specific exposure. | Historical settlement patterns, persistent local service trends, shared origin shocks, and past immigration can affect current outcomes directly. | Feasibility only. TAB4824 contains four background categories, not origin-specific stocks. |
| Recent administrative allocations | Municipal quotas, actual assignments, timing, allocation formula inputs, baseline controls | Assigned arrivals may affect current shares, but quotas and realized residence differ. | Allocation rules and direct municipal reception costs/caseloads may create a direct path to social-services duration. | Not adopted as a substitute for historical dispersal. The official settlement-statistics landing page is saved, not a validated Z file. |

## Historical dispersal construction and restrictions

IFAU's *Ethnic enclaves and welfare cultures* describes Sweden's 1985–1994 assignment policy and its stricter application in 1987–1991. Its discussion emphasizes housing availability and conditional placement practices. This historical institutional evidence supports investigating an assignment design; it does not establish that municipal refugee concentrations identify the effect of the foreign-born share on social-service duration forty years later. [IFAU working paper 2005:8](https://www.ifau.se/globalassets/pdf/se/2005/wp05-08.pdf), saved as `raw/ifau_refugee_dispersal.pdf`.

A candidate dose would be initial assigned refugees during a prespecified policy window divided by pre-policy municipal population. Use assignments, not later observed residence. Separate family-reunification or self-settling cases and retain assignment records and definitions. Harmonize historical municipalities to the 51 contemporary municipalities using official boundary concordances. Do not allocate historical totals across splits using guessed proportions. Preserve a missing Z if a defensible mapping is unavailable.

The historical policy could have persistent effects on housing segregation, poverty, service organization and staffing. Those are plausible direct determinants of investigation duration. Their existence is an exclusion-restriction concern even if Z strongly predicts the 2024 population share. Conditioning on current variables affected by historical placement can introduce further bias. Pre-policy covariates, pre-outcome trends, institutional records and an explicit estimand are required. A design originally justified for individual neighborhood exposure is not automatically justified for this aggregate municipal outcome.

## Shift-share construction

One conventional predicted inflow is

`Z_it = 100 / P_i0 * sum_o [ (M_io0 / M_o,Sweden,0) * DeltaM_o,Sweden,t ]`,

where `M_io0` is the stock from origin o in municipality i at a genuinely pre-shock date, `P_i0` is baseline population, and `DeltaM` is the corresponding national origin-specific inflow. Define the estimand and stock/flow concept before construction. For mechanical own-municipality correlation, construct a documented leave-one-municipality-out version, using both national stocks and shocks excluding municipality i consistently. A leave-one-out adjustment removes mechanical overlap; it does not prove shock exogeneity.

The national growth shocks and exposure stocks require origin-specific official data, geographic consistency, and treatment of changes in country classifications. Specify whether identification comes from exogenous shares or exogenous shocks, and justify that claim separately. Report shock concentration/effective shock count, exposure balance and sensitivity to dominant origins and base years. With incomplete exposure shares, relevant aggregate exposure controls may be needed. For parental-background measures, an origin-stock inflow prediction does not mechanically predict B or C: fertility, parental matching, aging and migration need an explicit first-stage rationale.

[Borusyak, Hull and Jaravel](https://www.nber.org/papers/w24997) explain shock-based identification and equivalent shock-level analysis. [Adão, Kolesár and Morales](https://www.nber.org/papers/w24944) show why conventional inference may be misleading with shared exposure shocks. [Jaeger, Ruist and Stuhler](https://www.nber.org/papers/w24285) discuss conflation of short- and long-run immigration responses. These source pages are saved in `raw/`. The proposals here are design assessments, not replications of those papers.

## Required diagnostics before any future 2SLS

1. Validate Z at municipality × year, with no duplicate keys, unreported missingness, guessed boundary allocation or researcher-imputed observations. Preserve both instrument components and denominators.
2. Fit each first stage on the exact complete-case estimation sample and with the same controls and fixed effects as the structural equation. Report excluded-instrument slopes, robust/clustered standard errors, partial R², and a first-stage strength test appropriate to the covariance/design. For heteroskedastic or clustered designs, report Kleibergen–Paap and/or an appropriate effective F rather than treating the homoskedastic F>10 rule as universal. Multiple endogenous measures need conditional first-stage diagnostics.
3. Use exposure/shock-aware inference for a shift-share design and recognize the limited number of independent shocks. Only three metros cannot support ordinary metro-cluster asymptotics.
4. Report weak-instrument-robust Anderson–Rubin confidence sets and, when justified and supported, conditional likelihood ratio inference. A strong first stage or a non-rejection of an overidentification test does not validate exclusion.
5. Present reduced-form results, balance and pretrend checks, alternate historical windows and base years, dominant-origin sensitivity, missing-Z selection, and spatial-spillover considerations. State the population and margin identified.
6. A fixed historical Z is absorbed by municipality effects. Any Z × time/shock construction needs its own identifying argument. Similarly, 2015 shares are omitted from municipality-FE specifications unless a specified interaction is used.

## Interpretation boundary

Even a future defensible municipal IV design would concern average municipality-level investigation duration under its identifying assumptions. U33401 does not distinguish migrant children, abuse types, urgency, time to emergency protection, or shelter placement. It cannot establish that an individual migrant child waits longer for protection. Individual-level linked investigation data and a different outcome definition would be needed for that question.
