# KPI definition and comparability audit

The saved metadata is a retrieval-time snapshot, not a year-versioned archive. The API exposes one current definition per KPI. It does not establish unchanged measurement in every municipality during 2022–2025.

## U33401
Mean days from opening to closing a social-services investigation for children/youth aged 0–20. Economic assistance, family-law and paternity investigations are excluded. The stated measurement period is the first half of the year. The source is the municipality's own survey. Collection continues throughout autumn and Kolada warns against comparisons before year-end. `count` in the response counts reporting units; it is not the number of investigations. Use gender T, never an average of female/male means.

This is not time to shelter placement, not a domestic-violence-specific outcome, and not a migrant-specific outcome. The child-background predictors concern ages 0–17, an explicit age mismatch with the outcome's 0–20 coverage.

## N02926
Foreign-born people divided by the number of inhabitants on 31 December, expressed in percent. Source: SCB Register of the Total Population (RTB). This is an all-age resident share, not the share among investigated children. We retain source percent and derive a 0–1 fraction.

Kolada's 2026-03-02 news item states that SCB introduced disclosure protection from population year 2025 by perturbing population counts with small random integers. The downloaded official N02926 values are used as published; we do not add noise, reverse it, or impute values. Its precise propagation to this KPI cannot be quantified from the returned metadata. A foreign-born-share panel sensitivity excludes 2025. The requested 2015 and 2024 counts in TAB4824 predate this change. Source: raw/kolada_home.html, https://www.kolada.se/.

## Year checks
All requested years have records for both KPIs. Coverage by municipality, year and metro is in coverage_by_year.csv. Missing outcome records are not zero investigations or zero days. No reporting completeness or case-volume denominator is supplied by these KPI responses. Municipality means are therefore unweighted by investigation volume.

RKA's official reporting page states that from 2025 RKA publishes submissions received via forms, replacing the input portal. The official 2025 KKiK changes document explicitly marks U33401 as collected in both 2024 and 2025, while the median KPI U33402 is discontinued after 2024. It discusses measurement and comparability problems as reasons for removing other KPIs. This does not by itself demonstrate a formula change in U33401. Year-specific 2022–2025 questionnaires or full definition-version histories were not authenticated. Consequently, unchanged historical definitions and consistent local application cannot be certified. The panel is exploratory and should be repeated after historical forms are obtained. See raw/rka_kkik_changes_2025_municipal_mirror.pdf and raw/rka_kkik_forms.html (the current page offers 2026 forms). The old extra.skr.se URL and its rka.nu counterpart returned HTTP 404 to Python; the document was recovered from Enköping municipality's official meeting archive. National and metro reporting coverage by year is in outcome_national_coverage.csv.

SCB TAB4824 covers 2002–2024 and was updated 2025-03-21. It supplies single ages and two sex categories. We sum exactly ages 0 through 17 and both sexes, within each of the four exhaustive background categories. We do not carry 2024 child shares into 2025. Counts are stocks on 31 December. A foreign-born child belongs to A irrespective of parental birthplace. C includes exactly one Sweden-born and one foreign-born parent, not all children with at least one foreign-born parent. Missing-parent classification rules are not separately documented in the retrieved table metadata and should not be reinterpreted from these aggregates.

Sources: [Kolada live metadata](https://api.kolada.se/v3/kpi/U33401,N02926), [RKA reporting](https://rka.nu/radetforframjandeavkommunalaanalyser/koladastod/publicerastatistikikolada.81664.html), [2025 KKiK changes](https://extra.skr.se/download/18.21af19d319762784ac14a0eb/1750176036743/F%C3%B6r%C3%A4ndringar%20i%20insamlingen%20av%20data%20till%20KKiK%202025.pdf), [SCB table](https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101Q/UtlSvBakgFin/).

## Exact current API metadata

```json
[
  {
    "id": "N02926",
    "title": "Utrikes födda, andel (%)",
    "description": "Antalet personer födda utomlands dividerat med antal invånare 31/12. Källa: Registret över totalbefolkningen (RTB)",
    "is_divided_by_gender": true,
    "municipality_type": "K",
    "auspice": "X",
    "operating_area": "Befolkning",
    "perspective": "Volymer",
    "prel_publication_date": null,
    "publication_date": "2027-02-24",
    "publ_period": "2026",
    "has_ou_data": false,
    "search_score": null
  },
  {
    "id": "U33401",
    "title": "Utredningstid i antal dagar från påbörjad utredning till avslutad utredning inom barn och ungdom 0-20 år, medelvärde",
    "description": "Genomsnittligt antal dagar från att utredningen påbörjats av socialtjänsten till dess att utredningen avslutats. Avser barn- och ungdom 0-20 år. Ekonomiskt bistånd, familjerätt och faderskapsutredningar är exkluderade. Mätperiod är första halvåret. Observera att datainsamling pågår hela hösten, varför medelvärden inte bör användas för jämförelser förrän i slutet av året. Källa: Egen undersökning i kommunen.",
    "is_divided_by_gender": true,
    "municipality_type": "K",
    "auspice": "T",
    "operating_area": "Individ- och familjeomsorg",
    "perspective": "Kvalitet och resultat",
    "prel_publication_date": null,
    "publication_date": null,
    "publ_period": null,
    "has_ou_data": false,
    "search_score": null
  }
]
```
