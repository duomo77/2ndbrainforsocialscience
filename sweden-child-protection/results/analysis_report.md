# Sweden metropolitan municipality associations

These are descriptive municipality-level associations. No coefficient is a causal effect, and no result identifies migrant children's individual protection delays.

## Outcome coverage and unweighted municipal means

| year | count | mean | std | median |
| --- | --- | --- | --- | --- |
| 2022 | 42 | 97.9524 | 15.8883 | 97.0000 |
| 2023 | 42 | 103.5714 | 12.6475 | 103.5000 |
| 2024 | 44 | 100.7023 | 13.4827 | 100.5000 |
| 2025 | 41 | 98.3501 | 14.0860 | 99.5567 |

## Primary 2024 metro fixed-effects OLS

Coefficients are days per one percentage point. HC3 standard errors, t-based intervals. Each predictor is estimated separately with metro indicators. BH adjustment covers the eight primary OLS slopes only; other reported analyses remain exploratory.

| predictor | n | coefficient | std_error | ci95_low | ci95_high | p_value | p_value_BH_primary_8 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| foreign_born_share | 44 | -0.2159 | 0.2262 | -0.6731 | 0.2414 | 0.3457 | 0.4194 |
| foreign_background | 44 | -0.1626 | 0.1532 | -0.4722 | 0.1469 | 0.2947 | 0.4194 |
| any_foreign_parent_among_Sweden_born | 44 | -0.1226 | 0.1453 | -0.4162 | 0.1710 | 0.4038 | 0.4194 |
| two_foreign_parents_among_Sweden_born | 44 | -0.1602 | 0.1606 | -0.4849 | 0.1644 | 0.3246 | 0.4194 |
| foreign_born_share_2015 | 44 | -0.2531 | 0.2827 | -0.8244 | 0.3182 | 0.3759 | 0.4194 |
| foreign_background_2015 | 44 | -0.1897 | 0.1772 | -0.5479 | 0.1685 | 0.2908 | 0.4194 |
| any_foreign_parent_among_Sweden_born_2015 | 44 | -0.1363 | 0.1671 | -0.4740 | 0.2014 | 0.4194 | 0.4194 |
| two_foreign_parents_among_Sweden_born_2015 | 44 | -0.1891 | 0.1931 | -0.5795 | 0.2012 | 0.3334 | 0.4194 |

None of these eight primary slopes is distinguishable from zero at the 5% level. Raw Pearson correlations for 2024 measures are close to zero. This is imprecise evidence, not proof that there is no relationship.

## 2024 raw correlations

| predictor | method | n | estimate | p_value |
| --- | --- | --- | --- | --- |
| foreign_born_share | pearson | 44 | 0.0420 | 0.7868 |
| foreign_born_share | spearman | 44 | 0.0869 | 0.5749 |
| foreign_background | pearson | 44 | 0.0145 | 0.9254 |
| foreign_background | spearman | 44 | 0.0558 | 0.7191 |
| any_foreign_parent_among_Sweden_born | pearson | 44 | 0.0518 | 0.7386 |
| any_foreign_parent_among_Sweden_born | spearman | 44 | 0.0833 | 0.5909 |
| two_foreign_parents_among_Sweden_born | pearson | 44 | 0.0162 | 0.9168 |
| two_foreign_parents_among_Sweden_born | spearman | 44 | 0.0242 | 0.8761 |

## 2024 metro outcome statistics

| metro | n_expected | n_observed | n_missing | mean | sd | median | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All 51 | 51 | 44 | 7 | 100.7023 | 13.4827 | 100.5000 | 67.0000 | 137.0000 |
| Stor-Göteborg | 13 | 11 | 2 | 92.0000 | 12.7984 | 95.0000 | 67.0000 | 112.0000 |
| Stor-Malmö | 12 | 11 | 1 | 103.9545 | 11.2126 | 105.0000 | 75.0000 | 117.0000 |
| Stor-Stockholm | 26 | 22 | 4 | 103.4273 | 13.4673 | 100.5000 | 86.0000 | 137.0000 |

## Short-panel estimates and sensitivity

| specification | predictor | n | n_municipalities | years | coefficient | std_error | ci95_low | ci95_high | p_value | p_value_BH_panel_4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OLS_municipality_year_FE | foreign_born_share | 169 | 45 | 2022,2023,2024,2025 | 5.7846 | 3.3259 | -0.9184 | 12.4876 | 0.0890 | 0.1014 |
| OLS_municipality_year_FE_balanced | foreign_born_share | 144 | 36 | 2022,2023,2024,2025 | 6.0500 | 3.8692 | -1.8048 | 13.9048 | 0.1269 |  |
| OLS_municipality_metro_by_year_FE | foreign_born_share | 169 | 45 | 2022,2023,2024,2025 | 3.8088 | 3.6213 | -3.4894 | 11.1071 | 0.2986 |  |
| OLS_municipality_year_FE_exclude_2025 | foreign_born_share | 126 | 43 | 2022,2023,2024 | 8.5638 | 5.0231 | -1.5732 | 18.7008 | 0.0956 |  |
| OLS_municipality_year_FE | foreign_background | 126 | 43 | 2022,2023,2024 | 5.3760 | 2.2783 | 0.7782 | 9.9739 | 0.0230 | 0.0460 |
| OLS_municipality_year_FE_balanced | foreign_background | 120 | 40 | 2022,2023,2024 | 5.1650 | 2.5655 | -0.0243 | 10.3542 | 0.0510 |  |
| OLS_municipality_metro_by_year_FE | foreign_background | 126 | 43 | 2022,2023,2024 | 4.7726 | 3.1671 | -1.6188 | 11.1641 | 0.1393 |  |
| OLS_municipality_year_FE | any_foreign_parent_among_Sweden_born | 126 | 43 | 2022,2023,2024 | 4.5971 | 2.7451 | -0.9427 | 10.1370 | 0.1014 | 0.1014 |
| OLS_municipality_year_FE_balanced | any_foreign_parent_among_Sweden_born | 120 | 40 | 2022,2023,2024 | 3.5916 | 2.8638 | -2.2010 | 9.3842 | 0.2173 |  |
| OLS_municipality_metro_by_year_FE | any_foreign_parent_among_Sweden_born | 126 | 43 | 2022,2023,2024 | 3.1996 | 3.8353 | -4.5405 | 10.9396 | 0.4089 |  |
| OLS_municipality_year_FE | two_foreign_parents_among_Sweden_born | 126 | 43 | 2022,2023,2024 | 6.6968 | 2.2472 | 2.1617 | 11.2318 | 0.0048 | 0.0191 |
| OLS_municipality_year_FE_balanced | two_foreign_parents_among_Sweden_born | 120 | 40 | 2022,2023,2024 | 6.5546 | 3.0582 | 0.3689 | 12.7404 | 0.0384 |  |
| OLS_municipality_metro_by_year_FE | two_foreign_parents_among_Sweden_born | 126 | 43 | 2022,2023,2024 | 6.5180 | 3.1818 | 0.0969 | 12.9391 | 0.0468 |  |

The main panel slopes are positive, in contrast to the negative metro-adjusted cross-section slopes. These models use different identifying variation and are not interchangeable. The child measures vary by less than one percentage point within a typical municipality in this short window. Balanced-panel and metro-by-year-effect sensitivities are reported alongside the main models. The four main panel p-values also receive a separate BH adjustment; sensitivity p-values are exploratory.

## 51-row 2024 coverage table

| municipality_code | municipality | metro | U33401_days | N02926_pct | children_total_0_17 | all_2024_measures_observed |
| --- | --- | --- | --- | --- | --- | --- |
| 0114 | Upplands Väsby | Stor-Stockholm |  | 35.6755 | 11369.0000 | False |
| 0115 | Vallentuna | Stor-Stockholm | 95.0000 | 16.7317 | 8331.0000 | True |
| 0117 | Österåker | Stor-Stockholm | 86.0000 | 18.1232 | 11395.0000 | True |
| 0120 | Värmdö | Stor-Stockholm | 125.0000 | 14.4119 | 10452.0000 | True |
| 0123 | Järfälla | Stor-Stockholm | 105.0000 | 36.4508 | 19529.0000 | True |
| 0125 | Ekerö | Stor-Stockholm | 96.0000 | 13.8983 | 7357.0000 | True |
| 0126 | Huddinge | Stor-Stockholm |  | 31.5711 | 26854.0000 | False |
| 0127 | Botkyrka | Stor-Stockholm |  | 44.2115 | 21950.0000 | False |
| 0128 | Salem | Stor-Stockholm | 103.0000 | 23.8305 | 4347.0000 | True |
| 0136 | Haninge | Stor-Stockholm | 127.0000 | 30.2869 | 23113.0000 | True |
| 0138 | Tyresö | Stor-Stockholm | 108.0000 | 18.2273 | 11308.0000 | True |
| 0139 | Upplands-Bro | Stor-Stockholm | 100.0000 | 33.9570 | 8040.0000 | True |
| 0140 | Nykvarn | Stor-Stockholm | 137.0000 | 15.5080 | 2991.0000 | True |
| 0160 | Täby | Stor-Stockholm |  | 20.2961 | 17587.0000 | False |
| 0162 | Danderyd | Stor-Stockholm | 106.0000 | 17.4865 | 7364.0000 | True |
| 0163 | Sollentuna | Stor-Stockholm | 102.0000 | 29.7975 | 17880.0000 | True |
| 0180 | Stockholm | Stor-Stockholm | 120.4000 | 26.3889 | 188314.0000 | True |
| 0181 | Södertälje | Stor-Stockholm | 90.0000 | 44.2100 | 22008.0000 | True |
| 0182 | Nacka | Stor-Stockholm | 90.0000 | 20.2316 | 26436.0000 | True |
| 0183 | Sundbyberg | Stor-Stockholm | 100.0000 | 33.7438 | 10970.0000 | True |
| 0184 | Solna | Stor-Stockholm | 97.0000 | 34.1827 | 14687.0000 | True |
| 0186 | Lidingö | Stor-Stockholm | 110.0000 | 18.3868 | 10751.0000 | True |
| 0187 | Vaxholm | Stor-Stockholm | 89.0000 | 10.9711 | 2442.0000 | True |
| 0188 | Norrtälje | Stor-Stockholm | 99.0000 | 13.9641 | 11851.0000 | True |
| 0191 | Sigtuna | Stor-Stockholm | 89.0000 | 38.8652 | 12484.0000 | True |
| 0192 | Nynäshamn | Stor-Stockholm | 101.0000 | 21.1779 | 6298.0000 | True |
| 1230 | Staffanstorp | Stor-Malmö | 117.0000 | 16.2913 | 7088.0000 | True |
| 1231 | Burlöv | Stor-Malmö | 104.0000 | 35.2221 | 4760.0000 | True |
| 1233 | Vellinge | Stor-Malmö |  | 9.7498 | 8754.0000 | False |
| 1261 | Kävlinge | Stor-Malmö | 99.0000 | 11.9377 | 7808.0000 | True |
| 1262 | Lomma | Stor-Malmö | 105.0000 | 10.6332 | 6152.0000 | True |
| 1263 | Svedala | Stor-Malmö | 102.0000 | 12.8620 | 6233.0000 | True |
| 1264 | Skurup | Stor-Malmö | 75.0000 | 14.6675 | 3749.0000 | True |
| 1267 | Höör | Stor-Malmö | 114.0000 | 11.8735 | 3932.0000 | True |
| 1280 | Malmö | Stor-Malmö | 100.0000 | 36.0361 | 75641.0000 | True |
| 1281 | Lund | Stor-Malmö | 112.5000 | 23.9418 | 24265.0000 | True |
| 1285 | Eslöv | Stor-Malmö | 109.0000 | 21.5795 | 7821.0000 | True |
| 1287 | Trelleborg | Stor-Malmö | 106.0000 | 18.7311 | 9880.0000 | True |
| 1384 | Kungsbacka | Stor-Göteborg | 93.0000 | 9.6081 | 19637.0000 | True |
| 1401 | Härryda | Stor-Göteborg | 97.0000 | 13.5140 | 9956.0000 | True |
| 1402 | Partille | Stor-Göteborg | 84.0000 | 21.6853 | 9863.0000 | True |
| 1407 | Öckerö | Stor-Göteborg | 112.0000 | 6.5226 | 2413.0000 | True |
| 1415 | Stenungsund | Stor-Göteborg | 102.0000 | 12.0211 | 6110.0000 | True |
| 1419 | Tjörn | Stor-Göteborg | 67.0000 | 9.1847 | 3002.0000 | True |
| 1440 | Ale | Stor-Göteborg |  | 18.7193 | 7844.0000 | False |
| 1441 | Lerum | Stor-Göteborg | 96.0000 | 11.2761 | 11083.0000 | True |
| 1462 | Lilla Edet | Stor-Göteborg | 95.0000 | 18.7024 | 3179.0000 | True |
| 1480 | Göteborg | Stor-Göteborg |  | 29.7598 | 115214.0000 | False |
| 1481 | Mölndal | Stor-Göteborg | 75.0000 | 19.8866 | 15435.0000 | True |
| 1482 | Kungälv | Stor-Göteborg | 89.0000 | 11.4265 | 11039.0000 | True |
| 1489 | Alingsås | Stor-Göteborg | 102.0000 | 12.4643 | 9318.0000 | True |

## Municipalities without a 2024 outcome

| municipality_code | municipality | metro |
| --- | --- | --- |
| 0114 | Upplands Väsby | Stor-Stockholm |
| 0126 | Huddinge | Stor-Stockholm |
| 0127 | Botkyrka | Stor-Stockholm |
| 0160 | Täby | Stor-Stockholm |
| 1233 | Vellinge | Stor-Malmö |
| 1440 | Ale | Stor-Göteborg |
| 1480 | Göteborg | Stor-Göteborg |

## Design and sensitivity

Pearson/Spearman and metro-partial correlations are in correlations.csv. Sensitivities include unadjusted OLS, log duration, child-population WLS, exclusion of the three core cities, balanced outcome reporters, and leave-one-municipality-out slopes. Child weighting changes the estimand and is not weighting by investigation counts. All official observations are retained; influence diagnostics do not justify silently deleting observations. Reporting_selection.csv compares the covariates of reporters and nonreporters, without assuming missingness at random.

Panel models use actual time-varying population shares, municipality and year effects, and municipality-clustered errors with finite-sample correction. N02926 can use 2022–2025; child-background measures use 2022–2024 only. Municipalities with only one complete observation are excluded. Balanced variants require all years in the corresponding estimation window. Within variation is reported in panel_identification.csv. No time-invariant 2015 share is included with municipality fixed effects.

Cross-section covariates for 2024 are year-end stocks whereas U33401 measures the first half-year. Reverse causality, omitted staffing/caseload, reporting selection, local measurement differences, population composition, spatial dependence and multiple testing limit interpretation. Three metros are too few for reliable metro-clustered inference; HC3 does not address spatial correlation. A municipal mean is not an individual risk or duration, and an ecological association cannot compare migrant and Sweden-born children.
