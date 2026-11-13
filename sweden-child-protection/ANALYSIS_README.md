# Sweden's 51 metropolitan municipalities: investigation duration and population background

Executed on **13 November 2026, Asia/Seoul**, using internet-enabled local Python on Windows. Google Colab was unnecessary because direct internet access worked. Exact UTC retrieval times, URLs, headers, HTTP statuses and SHA-256 hashes are in `raw/requests.jsonl`. The analysis uses official observations only and leaves missing observations blank.

## Findings and coverage

- SCB's live metropolitan aggregation crosswalk verifies **26 Stor-Stockholm, 13 Stor-Göteborg and 12 Stor-Malmö municipalities**. Codes and names also match Kolada. No supplied 51-code crosswalk was found in the workspace search.
- U33401 is observed for **42, 42, 44 and 41 municipalities** in 2022–2025 respectively. All 51 have N02926 for 2015 and 2022–2025. SCB background counts are complete for all 51 in 2015 and 2022–2024. TAB4824 ends in 2024: its 2025 fields are deliberately missing.
- In 2024 the unweighted mean of the 44 observed municipal investigation means is **100.70 days** (SD 13.48). Metro means: Stockholm **103.43** (22/26 reporters), Göteborg **92.00** (11/13), Malmö **103.95** (11/12). These are not case-volume-weighted investigation means.
- The primary 2024 metro-FE coefficient for the foreign-born resident share is **−0.216 days per percentage point**, HC3 95% CI **[−0.673, 0.241]**. None of the eight primary 2024 slopes, covering four measures at 2015 and 2024, rejects zero at 5%. This is not evidence of equivalence or proof of no relationship.
- Short-panel estimates are positive and some are nominally significant. Coverage, limited within-municipality variation, balanced-panel checks, metro-by-year effects and multiple comparisons affect interpretation. See `results/analysis_report.md`, not just the cross-section headline.
- No defensible Z was validated. **No 2SLS was run.** See `results/iv_audit.md` for construction proposals, exclusion concerns and required weak-IV diagnostics.

## Deliverables

| Path | Contents |
| --- | --- |
| `raw/` | Unmodified official response bodies, full 24.5 MB SCB ZIP, live API schemas, KPI/table metadata, SCB metro classification, source documents and HTTP request/error log |
| `data/metro_51_2024.csv` | Exactly 51 municipality rows, 2024 outcomes/shares/counts, 2015 baselines, retained numerators/denominators and availability flags |
| `data/metro_51_panel.csv` | Exactly 204 municipality × year rows for 2022–2025; absent measurements stay blank |
| `data/municipality_crosswalk.csv` | Four-digit municipal codes, official names, metro labels/codes |
| `data/kolada_metro_long.csv` | All returned metro KPI observations by sex, status, value, reporting-unit count and deletion flag |
| `data/child_background_age_sex_long.csv` | 29,376 official selected SCB cells before age/sex aggregation |
| `data/child_background_counts_shares.csv` | 204 municipality × year rows for 2015, 2022, 2023 and 2024; four counts and derived shares |
| `results/coverage.csv` | Full 51-row 2024 coverage table |
| `results/coverage_by_year.csv` | Metro and all-51 missingness for every measure/year |
| `results/outcome_national_coverage.csv` | National municipal and metro outcome coverage by year |
| `results/descriptives.csv` | Unweighted municipal statistics by metro/year plus the combined sample |
| `results/descriptives_baseline_comparison.csv` | Metro and all-51 mean shares in 2015 and 2024, plus percentage-point changes |
| `results/metro_pooled_child_shares.csv` | Pooled child shares calculated from summed numerators/denominators |
| `results/regressions.csv` | Separate predictor OLS/WLS models, HC3 or municipal-clustered SEs, CIs, p-values, sample sizes and units |
| `results/correlations.csv` | Pearson/Spearman and metro-partial correlations for 2015/2024 predictors against the 2024 outcome |
| `results/leave_one_out.csv`, `results/influence.csv` | Municipality deletion sensitivity, leverage and Cook's distance |
| `results/reporting_selection.csv` | Reporter/nonreporter covariate comparisons; descriptive Welch tests |
| `results/panel_identification.csv` | Actual panel windows and within-municipality variation |
| `results/panel_followup.md`, `results/panel_same_sample_comparison.csv` | Same-municipality cross-section/panel comparison and combined balanced/metro-by-year sensitivity; reproduce with `python panel_followup.py` |
| `results/two_parent_influence_report.md`, `results/two_parent_*.csv`, `results/two_parent_first_differences.png` | Full municipality/cell influence diagnostics and adjacent-year versus endpoint first differences; reproduce with `python panel_influence.py` |
| `results/analysis_report.md` | Findings, full 51-row coverage table, panel estimates and interpretation |
| `results/kpi_metadata_audit.md` | Definitions, units, age/reference-period mismatches and year-comparability evidence/gaps |
| `results/iv_audit.md` | Feasibility only; no invented first-stage or IV estimates |
| `results/2024_associations.png` | Static municipal scatterplots, visually inspected |
| `results/validation.csv`, `results/independent_checks.csv` | Data validation and independent numerical checks |
| `results/raw_checksums.csv`, `results/source_manifest.csv` | Checksums and source-to-response provenance |
| `results/fetch_diagnostics.md` | Exact retrieval failures, fallbacks and runtime corrections |
| `analysis.py`, `retrieve.py`, `fetch_scb.py`, `verify.py`, `package.py` | Reproducible retrieval, analysis, verification and ZIP packaging |

## Exact commands

PowerShell, from this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONIOENCODING='utf-8'
python retrieve.py
python fetch_scb.py
python analysis.py
python panel_followup.py
python panel_influence.py
python verify.py
python package.py
```

Or execute in a Linux/Colab Python environment after uploading/unzipping this folder:

```bash
python -m pip install -r requirements.txt
python analysis.py
python panel_followup.py
python panel_influence.py
python verify.py
python package.py
```

The analysis, follow-up, influence, verification and packaging commands reproduce results **offline from the saved raw files**. `analysis.py` streams the compressed SCB archive (494,549,316 uncompressed bytes) without extracting a 495 MB file, and compares all 29,376 selected API cells exactly. It takes several seconds. `--skip-bulk-check` explicitly skips only that comparison, but was **not** used for the delivered validation.

Downloads use an existing successfully logged, checksum-matching cache; failed HTTP responses are never accepted as data. `retrieve.py` tests the old RKA PDF URL, which currently returns 404, and also downloads the official municipal archive mirror. See diagnostics. For refreshed observations, use a new output copy with an empty `raw/`, run both retrieval scripts, inspect diagnostics, then rerun analysis. Do not mix a newly fetched source with stale analysis results.

Read municipal codes as text:

```python
import pandas as pd
df = pd.read_csv('data/metro_51_2024.csv', dtype={'municipality_code': str, 'metro_code': str})
```

CSV files use UTF-8 with BOM, decimal points and empty numeric cells for missing values. Four-digit codes are preserved in the files. Excel's automatic CSV import may strip leading zeros: import those columns as text. There are no synthetic observations or mean/zero/carry-forward imputations. The balanced grid includes missing-data placeholders, not generated measurements.

## Definitions and dictionary

SCB background codes, verified against live table metadata:

| Group | SCB code | Exact category label |
| --- | --- | --- |
| A | `08` | utrikes födda |
| B | `4` | inrikes födda med två utrikes födda föräldrar |
| C | `5` | inrikes födda med en inrikes och en utrikes född förälder |
| D | `6` | inrikes födda med två inrikes födda föräldrar |

Sum single ages **0 through 17 inclusive** and sexes `1` (män), `2` (kvinnor). Each background count aggregates exactly 36 cells. Categories partition the published population. Source classification of unknown parent birthplace is not separately established from the table metadata.

- `foreign_background = (A+B)/(A+B+C+D)`.
- `any_foreign_parent_among_Sweden_born = (B+C)/(B+C+D)`.
- `two_foreign_parents_among_Sweden_born = B/(B+C+D)`.
- `children_total_0_17 = A+B+C+D`; `sweden_born_children_0_17 = B+C+D`. Numerator columns are retained. `A_foreign_born`, `B_sweden_born_two_foreign_parents`, `C_sweden_born_one_foreign_parent`, `D_sweden_born_two_sweden_parents` contain counts.
- `N02926_pct` is source percentage; `foreign_born_share = N02926_pct/100`. Its denominator is **all registered residents on 31 December**, all ages. This differs from the three child denominators.
- Suffix `_2015` denotes a true 2015 baseline repeated across panel rows for joining; it is never used as a contemporaneous observation. Un-suffixed fields always refer to `year`.
- `U33401_days` uses sex `T` (total), not an average of sex-specific means. `_source_status`, `_isdeleted`, `_usable`, `_reporting_unit_count` retain API flags. The latter is **not case volume**. `*_availability` distinguishes observed, absent total record and flagged/deleted data. All seven 2024 outcome gaps are absent total records.
- Shares in data files are fractions [0,1], except columns explicitly named `_pct`. Regression coefficients multiply the chosen share by 100, so the scale is **one percentage point**. Log-outcome coefficients are log days per point.

## Statistical specifications

For each of four measures, separately at 2024 and 2015, the primary model is `U33401_days ~ 100*share + metro indicators` on complete 2024 observations (n=44), with HC3 covariance and t(n−k) intervals. Primary slopes receive BH correction as one family of eight. Pearson/Spearman correlations are pairwise complete-case; partial Spearman ranks before residualizing metro indicators, with an approximate t reference distribution.

Sensitivities: no metro controls, log duration, child-population weights, exclusion of Stockholm/Göteborg/Malmö cores (Göteborg has no 2024 outcome already), municipalities reporting outcomes in all four years, and leave-one-out slopes. Child weighting targets a different municipal weighting and does not recover case-level averages. No outlier is silently removed.

Panel models use time-varying shares, municipality FE and year FE. Municipality-clustered errors use a finite-sample correction and t(G−1) reference. Require at least 60 complete observations, 20 municipalities and three years; exclude singleton municipalities. Also fit balanced panels and metro-specific year shocks. The child panel ends in 2024. A N02926 sensitivity excludes 2025 because of SCB's newly introduced disclosure protection. Four primary panel slopes form a separate BH family. Sensitivity p-values and correlation p-values remain exploratory. **No time-invariant 2015 share is included with municipality fixed effects.**

## Official sources

1. [SCB metropolitan classification index](https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/funktionella-regioner-och-kommungrupper/), [live aggregation and municipality membership](https://statistikdatabasen.scb.se/api/v2/codeLists/agg_RegionStoromr05-_1?lang=sv), and linked XLS/PDF, all saved.
2. [Kolada API v3 docs](https://api.kolada.se/v3/docs), [live OpenAPI](https://api.kolada.se/v3/openapi.json), [KPI metadata](https://api.kolada.se/v3/kpi/U33401,N02926), [free search](https://www.kolada.se/verktyg/fri-sokning/). Data paths were selected **after** inspecting the downloaded live schema. All nine KPI-year responses have `next_url=null` and returned counts match response lengths.
3. [SCB UtlSvBakgFin / TAB4824 table](https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101Q/UtlSvBakgFin/), [live v2 schema](https://statistikdatabasen.scb.se/swagger/v2/swagger.json), [table metadata](https://statistikdatabasen.scb.se/api/v2/tables/TAB4824/metadata?lang=sv), [bulk ZIP](https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB4824_sv.zip). The table was updated 2025-03-21 and covers 2002–2024. Units: persons; reference date: 31 December. Saved POST body: `raw/scb_child_query.json`.
4. [RKA reporting process](https://rka.nu/radetforframjandeavkommunalaanalyser/koladastod/publicerastatistikikolada.81664.html), [current forms](https://rka.nu/radetforframjandeavkommunalaanalyser/koladastod/publicerastatistikikolada/formularinrapporteringforkkik.44880.html), [official Enköping meeting-archive copy of RKA's 2025 collection changes](https://politik.enkoping.se/welcome-sv/namnder-styrelser/kommunfullmaktige/kommunfullmaktige-2025-11-04/agenda/forandringar-i-insamlingen-av-data-till-kkik-2025pdf?downloadMode=download). U33401 remains collected in 2025, whereas U33402 is discontinued. The submission process changed in 2025. Full annual definition histories for 2022–2025 remain unverified.
5. [Kolada news](https://www.kolada.se/) documents SCB's population disclosure-protection change from 2025. Published official data are retained as supplied. Instrument-design sources are cited in `results/iv_audit.md` and saved in `raw/`.

## Limitations

U33401 covers **first-half-year investigations for ages 0–20**, excluding economic assistance, family-law and paternity investigations. It is not a full-year population register outcome, not time to shelter placement and not specific to domestic violence or migrants. Collection is voluntary/local and continues through autumn; current metadata does not authenticate every historical local implementation. 2024 predictors are year-end stocks, temporally after the outcome's measurement window. The child shares cover 0–17, and N02926 covers all ages.

Missing outcomes, absence of investigation-volume weights, omitted staffing/caseload, measurement differences, short-panel changes, spatial dependence and multiple testing limit inference. Three metros are insufficient for ordinary metro-cluster asymptotics. Municipal fixed effects do not remove time-varying confounding. There is no individual linkage: municipal associations cannot show that migrant children wait longer for protection.
