# Which municipalities support the two-parent panel association?

Run `python panel_influence.py`. All calculations use the previously saved official 2022–2024 observations. The exposure is 100 × B/(B+C+D), the percentage of Sweden-born children aged 0–17 with two foreign-born parents. No new downloads or imputation were used. Coefficients are days per one percentage point. Every model is re-estimated after a deletion, including all fixed effects and its covariance correction.

## Findings

The positive slope is not attributable to one municipality or one cell alone: every single-municipality and single-cell deletion in the original model leaves a positive slope. Statistical evidence is materially concentrated, however. Öckerö, Nynäshamn and Upplands-Bro together account for about 71% of the signed cross-product between exposure and outcome after removing municipality and year effects. This percentage is a contribution to the regression numerator, not R², a share of cases, or a causal attribution. It conditions on the full-sample residualization, whereas deletion re-estimates that residualization.

The main slope is +6.697 (p=.0048). Omitting Öckerö gives +5.642 (p=.0068); omitting Nynäshamn gives +6.032 (p=.0175); omitting Upplands-Bro gives +6.037 (p=.0574). The last omission weakens precision substantially because Upplands-Bro supplies considerable exposure variation. Across all 43 omissions the slope ranges from +5.642 to +7.168, and 42 of the 43 tests have p<.05. Hence the sign is stable to one municipality, but the 5% classification is not completely stable.

Deleting the three strongest supporting municipalities together gives +3.210, 95% CI [−2.505, 8.926], p=.263. Removing the five strongest gives +1.096 (p=.690). These groups are selected after inspecting influence: they are stress tests, not a defensible reason to discard valid observations or infer that the original estimate is spurious.

## Municipal influence in the original model

| municipality_code | municipality | coefficient_omitting_municipality | p_omitting_municipality | covariance_share | partial_x_information_share |
| --- | --- | --- | --- | --- | --- |
| 1407 | Öckerö | 5.6424 | 0.0068 | 0.1739 | 0.0240 |
| 0192 | Nynäshamn | 6.0316 | 0.0175 | 0.1903 | 0.1037 |
| 0139 | Upplands-Bro | 6.0370 | 0.0574 | 0.3565 | 0.2889 |
| 1230 | Staffanstorp | 6.1120 | 0.0116 | 0.0889 | 0.0041 |
| 1231 | Burlöv | 6.3704 | 0.0082 | 0.0710 | 0.0246 |

The first three rows account for approximately 71.1% of the signed residual covariance and 41.7% of the residual exposure sum of squares. Staffanstorp and Burlöv are additional supporting municipalities.

## All leave-one-municipality-out ranges

| specification | slope_min | slope_max | p_min | p_max | n_significant_05 | n_omissions |
| --- | --- | --- | --- | --- | --- | --- |
| TWFE_balanced | 5.1592 | 7.2581 | 0.0232 | 0.1167 | 33 | 40 |
| TWFE_unbalanced | 5.6424 | 7.1681 | 0.0023 | 0.0574 | 42 | 43 |
| municipality_metro_year_balanced | 4.3881 | 7.1456 | 0.0916 | 0.2737 | 0 | 40 |
| municipality_metro_year_unbalanced | 5.3429 | 7.3975 | 0.0273 | 0.1787 | 26 | 43 |

The balanced sample has 40 municipalities; its slope remains positive under all omissions but is significant in 33/40. With metro-specific year effects, it is significant in 26/43 unbalanced omissions and 0/40 balanced omissions. These are exploratory unadjusted p-values, not independent tests.

## Influential individual municipality-year observations

Öckerö/2022, Tjörn/2024 and Nynäshamn/2022 are the three single cells whose removal most reduces the original slope. Removing Öckerö/2022 alone gives +5.633 (p=.0069). Removing Öckerö/2022 and Tjörn/2024 together gives +4.812, 95% CI [−0.399, 10.022], p=.0694; adding Nynäshamn/2022 gives +3.988 (p=.164).

Upplands-Bro has outcomes only in 2022 and 2024. Removing either leaves a singleton that contributes no within-municipality information, so the remaining singleton is also excluded from FE estimation. The cell-deletion files report actual rows removed; this case is equivalent to omitting the municipality, not a pure one-row influence contrast. All other deleted cells are observed official values, not identified data errors.

| omitted_code | omitted_municipality | omitted_year | actual_rows_removed | coefficient | p_value |
| --- | --- | --- | --- | --- | --- |
| 1407 | Öckerö | 2022 | 1 | 5.6327 | 0.0069 |
| 1419 | Tjörn | 2024 | 1 | 5.9462 | 0.0364 |
| 0192 | Nynäshamn | 2022 | 1 | 6.0032 | 0.0153 |
| 0139 | Upplands-Bro | 2022 | 2 | 6.0370 | 0.0574 |
| 0139 | Upplands-Bro | 2024 | 2 | 6.0370 | 0.0574 |
| 1230 | Staffanstorp | 2024 | 1 | 6.1258 | 0.0114 |
| 0140 | Nykvarn | 2024 | 1 | 6.3463 | 0.0125 |
| 1231 | Burlöv | 2023 | 1 | 6.3517 | 0.0077 |

## Actual trajectories behind the influence

| municipality_code | municipality | year | x_pp | U33401_days |
| --- | --- | --- | --- | --- |
| 0139 | Upplands-Bro | 2022 | 33.9623 | 75.0000 |
| 0139 | Upplands-Bro | 2024 | 37.2918 | 100.0000 |
| 0192 | Nynäshamn | 2022 | 18.6730 | 79.0000 |
| 0192 | Nynäshamn | 2023 | 19.9893 | 100.0000 |
| 0192 | Nynäshamn | 2024 | 20.9290 | 101.0000 |
| 1230 | Staffanstorp | 2022 | 14.4886 | 65.0000 |
| 1230 | Staffanstorp | 2023 | 15.0699 | 73.0000 |
| 1230 | Staffanstorp | 2024 | 15.4724 | 117.0000 |
| 1231 | Burlöv | 2022 | 39.8139 | 103.0000 |
| 1231 | Burlöv | 2023 | 40.5160 | 122.0000 |
| 1231 | Burlöv | 2024 | 40.0188 | 104.0000 |
| 1407 | Öckerö | 2022 | 1.9287 | 140.0000 |
| 1407 | Öckerö | 2023 | 1.6949 | 111.0000 |
| 1407 | Öckerö | 2024 | 1.9031 | 112.0000 |
| 1419 | Tjörn | 2022 | 5.2343 | 69.0000 |
| 1419 | Tjörn | 2023 | 4.9756 | 113.0000 |
| 1419 | Tjörn | 2024 | 4.9221 | 67.0000 |

Upplands-Bro combines a +3.33 pp two-parent-share change with a +25-day duration change between 2022 and 2024, but its missing 2023 outcome cannot be interpolated. Nynäshamn combines approximately +2.26 pp with +22 days. Staffanstorp combines approximately +0.98 pp with +52 days. Öckerö's share is almost flat across the endpoints, while its duration falls from 140 to 112 days. It contributes positively after adjustment because its exposure trajectory is compared with the common year pattern; influence is not determined by the raw endpoint change alone. Tjörn's duration is volatile (69, 113, 67 days), despite a much smaller exposure change.

## First differences

Annual first-difference regressions use only actually observed consecutive pairs, with interval indicators for common year changes. No 2022–2024 gap is treated as a one-year difference. Standard errors are municipality-clustered for pooled annual differences. Separate annual or endpoint cross-sections use HC3 errors and t(n−k) intervals. Adding metro × interval indicators allows different annual shocks in each metro. In the endpoint model, an intercept and metro indicators absorb common and metro-specific two-year changes.

| specification | n | municipalities | coefficient | std_error | ci95_low | ci95_high | p_value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FD_adjacent_unbalanced | 82 | 42 | 4.2490 | 3.5048 | -2.8292 | 11.3272 | 0.2323 |
| FD_adjacent_balanced | 80 | 40 | 5.1219 | 3.4717 | -1.9002 | 12.1439 | 0.1482 |
| FD_adjacent_metro_interval_unbalanced | 82 | 42 | 4.0647 | 4.1509 | -4.3181 | 12.4475 | 0.3332 |
| FD_adjacent_metro_interval_balanced | 80 | 40 | 4.8514 | 4.1161 | -3.4742 | 13.1770 | 0.2457 |
| FD_2022_2023 | 41 | 41 | 3.3750 | 8.2235 | -13.2586 | 20.0087 | 0.6838 |
| FD_2022_2023_metro_controls | 41 | 41 | 4.4541 | 7.6014 | -10.9478 | 19.8560 | 0.5615 |
| FD_2023_2024 | 41 | 41 | 5.1876 | 5.3192 | -5.5715 | 15.9466 | 0.3354 |
| FD_2023_2024_metro_controls | 41 | 41 | 3.6636 | 6.7619 | -10.0374 | 17.3646 | 0.5912 |
| FD_endpoint_2022_2024 | 41 | 41 | 7.7439 | 1.6445 | 4.4175 | 11.0703 | 0.0000 |
| FD_endpoint_2022_2024_metro_controls | 41 | 41 | 7.4343 | 2.5271 | 2.3140 | 12.5546 | 0.0056 |

The pooled adjacent-year result is positive but imprecise: +4.249 (p=.232), or +4.065 (p=.333) with metro-specific interval changes. It remains imprecise on the balanced sample. Neither single annual interval yields a precise association. All adjacent-year first-difference slopes remain positive when any one municipality is omitted, but none of the 42 original unbalanced annual-difference omission models has p<.05.

The two-year endpoint result is substantially stronger: +7.744 (p=.000031), or +7.434 with metro controls, 95% CI [2.314, 12.555], p=.0056. Its metro-controlled slope remains positive and significant under all 41 single-municipality omissions: +6.248 to +8.435, with maximum p=.04794. Omitting Upplands-Bro leaves the 40 complete municipalities and gives +6.836 (p=.04794). Thus endpoint evidence cannot be dismissed as one municipality alone.

For the metro-controlled endpoint result, the three strongest supporting municipalities by single-omission change are Staffanstorp, Österåker and Nynäshamn. Removing those together gives +4.641, 95% CI [−0.613, 9.894], p=.0815; removing the five strongest gives +1.829 (p=.493). The no-metro endpoint model remains significant after its own top three are removed (+5.531, p=.0176) but not after its top five (+2.716, p=.285). Different controls give different influence rankings; these deletions must not be presented as a prespecified sample.

Three-wave levels FE, pooled annual differences and a two-year endpoint difference weight the changes differently, so their slopes and uncertainty need not match. Upplands-Bro contributes to the levels/endpoint models but not adjacent-year differences because 2023 is missing; nevertheless, balanced annual-difference models are also imprecise. Endpoint differences discard the intermediate 2023 outcome and can attenuate short-lived fluctuations. This is a possible explanation for the precision difference, not an identified error process or proof of a long-run effect.

## Assessment

A positive direction persists across most specifications and every single-municipality omission in the principal and first-difference models. Evidence of a precisely estimated association is sensitive to a small set of municipalities or cells and to the time interval. The finding is stronger for the 2022–2024 endpoint change than for individual annual changes. It is not a robust causal result, nor is it demonstrably just one erroneous outlier. No influential observations were deleted from the delivered core datasets.

These are municipal investigation-duration associations. They cannot establish individual migrant children's protection delays, domestic-violence delays or time to shelter placement. The exposure is a year-end child-population stock whereas the outcome covers first-half-year investigations for ages 0–20.

## Files and checks

- `two_parent_leave_one_municipality_out.csv`: all 166 municipal deletions across four specifications.
- `two_parent_leave_one_cell_out.csv`: all 246 cell deletions for the primary and balanced metro-year models, including actual rows removed.
- `two_parent_municipality_contributions.csv`, `two_parent_residualized_observations.csv`: signed covariance and exposure-information contributions.
- `two_parent_cumulative_deletions.csv`: multiple municipal/cell stress tests, with exact omissions.
- `two_parent_first_differences.csv`, `two_parent_endpoint_differences.csv`: observed changes with retained endpoints.
- `two_parent_first_difference_models.csv`, `two_parent_first_difference_leave_one_out.csv`, `two_parent_first_difference_cumulative_deletions.csv`: FD estimates and influence checks.
- `two_parent_influential_observed_values.csv`: actual exposure numerators, denominators and outcomes for the principal municipalities.
- `two_parent_influence_checks.csv`: original-estimate reproduction, residual decompositions and two-wave-FE/endpoint equivalence.

All covariance calculations were independently checked by direct matrix algebra for each fitted model, including deletion models. Raw input checksums and the earlier source validation remain unchanged. All p-values here are exploratory, with no correction for the many deletion/specification comparisons. Failure to reject after deletion is not evidence of a zero coefficient.
