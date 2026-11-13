# Panel fixed effects: interpretation and combined sensitivity

Follow-up analysis of the saved official observations. No additional data download or imputation was performed. Run `python panel_followup.py` to reproduce `panel_same_sample_comparison.csv`. The original estimates remain in `regressions.csv`.

Additional requested influence and first-difference checks are in `two_parent_influence_report.md`. They show positive slopes under every single-municipality omission, substantial concentration in a few municipalities/cells, imprecise adjacent-year differences, and a stronger 2022–2024 endpoint association. These checks supplement the combined-control sensitivity below.

## Primary panel results

Each measure enters separately with municipality and year fixed effects. Coefficients are days per one percentage point. Errors are clustered by municipality, with finite-sample correction and t(G−1) intervals. All regressors are contemporaneous time-varying shares, not repeated 2015 baseline values.

| Measure | Years | Observations / municipalities | Coefficient | 95% CI | p | BH q, four primary panel slopes |
| --- | --- | --- | --- | --- | --- | --- |
| Foreign-born share, all residents | 2022–2025 | 169 / 45 | 5.785 | −0.918 to 12.488 | .0890 | .1014 |
| Foreign background, all children aged 0–17: (A+B)/(A+B+C+D) | 2022–2024 | 126 / 43 | 5.376 | 0.778 to 9.974 | .0230 | .0460 |
| Any foreign-born parent among Sweden-born children: (B+C)/(B+C+D) | 2022–2024 | 126 / 43 | 4.597 | −0.943 to 10.137 | .1014 | .1014 |
| Two foreign-born parents among Sweden-born children: B/(B+C+D) | 2022–2024 | 126 / 43 | 6.697 | 2.162 to 11.232 | .0048 | .0191 |

BH adjustment here applies only to these four primary panel slopes. The many sensitivity specifications are exploratory.

## Why the cross-section and panel differ

The 2024 metro-FE cross-section asks whether municipalities with higher population shares have longer duration than other municipalities in the same metro. The panel asks whether a municipality's deviations in population share over time covary with its deviations in investigation duration, after removing municipality constants and common year shocks. This is a different source of identifying variation. Between-municipality and within-municipality covariance need not have the same sign.

The sign difference is not solely a consequence of changing the set of municipalities. Restricting to the same 40 municipalities observed in all three years 2022–2024, the two-foreign-born-parents measure gives a 2024 metro-FE coefficient of −0.105 days/pp (p=.576), and a panel coefficient of +6.555 days/pp (p=.038). The other three measures show the same near-zero cross-section/positive panel pattern on this common sample. This demonstrates a difference in variation used; it does not establish which estimate is causal or identify a particular confounder.

After removing both municipality and year effects on the common 40-municipality sample, the exposure residual SD is only 0.20–0.34 percentage points (0.268 pp for the two-parent measure). A one-point coefficient describes a change large relative to this narrow residual variation. Municipal staffing, changing case composition, service demand, local trends or reporting changes could affect duration alongside population composition. These mechanisms are not identified by the present dataset. Year effects remove common national shocks, not every local trend.

## Which findings survive

| Measure | Primary p | Balanced-panel p | Metro-by-year effects p | Balanced and metro-by-year effects together p |
| --- | --- | --- | --- | --- |
| Foreign-born resident share | .0890 | .1269 | .2986 | .2461 |
| Foreign background, ages 0–17 | .0230 | .0510 | .1393 | .2139 |
| Any foreign-born parent among Sweden-born children | .1014 | .2173 | .4089 | .6164 |
| Two foreign-born parents among Sweden-born children | .0048 | .0384 | .0468 | .1404 |

The original foreign-born-share balanced model covers 36 municipalities in 2022–2025. The original child balanced models cover 40 municipalities in 2022–2024. The combined new sensitivity uses the same 40 municipalities and 120 observations in 2022–2024 for every measure, allowing all measures to be compared on identical observations. Consequently, the foreign-born comparison also changes the time window; it is not an isolated test of metro-specific year effects. In its separate original 2022–2024, unbalanced sensitivity, the foreign-born slope is 8.564 (p=.0956).

The two-parent share is the strongest signal and remains positive and nominally significant when either original restriction is applied separately. When both restrictions are combined, its coefficient is +6.074 days/pp, clustered SE 4.036, 95% CI [−2.090, 14.239], p=.1404. The point estimate changes moderately while uncertainty increases considerably. No panel association remains significant at 5% in this combined sensitivity. All four point estimates remain positive, so there is sign stability but not robust statistical precision. The weaker foreign-background result loses significance in the balanced or metro-by-year checks. The other two measures were not significant at 5% in the primary panel.

This does not prove no association. It shows that the positive panel evidence depends on the specification and available precision. The three-year child panel cannot resolve persistent municipal trends convincingly. Municipality-level investigation duration, ages 0–20 during the first half-year, remains a different outcome from individual migrant children's protection or placement delays. The predictors are year-end population stocks, further limiting temporal interpretation. No causal claim or IV estimate follows from these results.

## Verification

The combined design matrices were checked for full rank. Coefficients and municipality-clustered standard errors were reproduced independently with direct matrix algebra, including the G/(G−1) × (N−1)/(N−K) covariance correction.
