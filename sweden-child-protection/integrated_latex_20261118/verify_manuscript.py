"""Recalculate the main estimates and check the tables against packaged data."""
from collections import Counter
from pathlib import Path
import json
import re

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent
CASE2 = ROOT / "reproduction"
tables = {
    item["label"]: item["rows"]
    for item in json.loads((ROOT / "table_transcription.json").read_text(encoding="utf-8"))
}
source = (ROOT / "main.tex").read_text(encoding="utf-8")
assert Counter(re.findall(r"\\label\{tab:([^}]+)\}", source)) == Counter(tables.keys())
abstract = source.split(r"\begin{abstract}", 1)[1].split(r"\end{abstract}", 1)[0]
assert "263개 연결표본" in abstract and "두 해 모두 35개" in abstract
assert "17개에서 31개" not in abstract
panel = pd.read_csv(ROOT / "data/metro_51_panel.csv", dtype={"municipality_code": str})
assert len(panel) == 204
assert panel.municipality_code.nunique() == 51
assert panel.municipality_code.str.fullmatch(r"\d{4}").all()
assert not panel.duplicated(["municipality_code", "year"]).any()
assert panel.groupby("year").U33401_days.count().to_list() == [42, 42, 44, 41]
predictors = [
    "foreign_born_share", "foreign_background",
    "any_foreign_parent_among_Sweden_born", "two_foreign_parents_among_Sweden_born",
]
assert panel.loc[panel.year.eq(2025), predictors[1:]].isna().all().all()
annual = panel.loc[panel.year.eq(2024) & panel.U33401_days.notna()]
assert f"{annual.U33401_days.mean():.2f}" == "100.70"
assert f"{annual.U33401_days.std():.2f}" == "13.48"

def check_fit(fit, row, offset, decimals):
    coefficient, interval, p_value = row[offset:offset + 3]
    np.testing.assert_allclose(fit.params["x"], float(coefficient), atol=0.5 * 10**-decimals)
    low, high = (float(v) for v in interval.strip("[]").split(","))
    np.testing.assert_allclose(fit.conf_int().loc["x"], [low, high], atol=0.005)
    np.testing.assert_allclose(fit.pvalues["x"], float(p_value), atol=0.0005)

for index, predictor in enumerate(predictors):
    cross = annual.assign(x=100 * annual[predictor])
    fit = smf.ols("U33401_days ~ x + C(metro)", cross).fit(cov_type="HC3", use_t=True)
    check_fit(fit, tables["cross"][index], offset=1, decimals=3)
    usable = panel.dropna(subset=["U33401_days", predictor]).copy()
    count = usable.groupby("municipality_code").municipality_code.transform("size")
    usable = usable.loc[count.ge(2)].assign(x=lambda rows: 100 * rows[predictor])
    fit = smf.ols("U33401_days ~ x + C(municipality_code) + C(year)", usable).fit(
        cov_type="cluster", cov_kwds={"groups": usable.municipality_code}, use_t=True
    )
    assert tables["panel"][index][1] == f"{len(usable)}/{usable.municipality_code.nunique()}"
    check_fit(fit, tables["panel"][index], offset=2, decimals=2)

wide = pd.read_csv(CASE2 / "data/municipality_analysis_wide.csv", dtype={"code": str})
long = wide[wide.long_panel]
linked = wide[wide.linked_2025_2026]
assert (len(wide), len(long), len(linked), long.y2024.count()) == (290, 191, 263, 190)
high = "high_foreign_2015"
for year, high_cell, comparison_cell, gap in tables["c2levels"]:
    ones = long.groupby(high)[f"y{year}"].sum()
    assert high_cell == f"{ones[1]:.0f}/51" and comparison_cell == f"{ones[0]:.0f}/140"
    assert f"{100 * (ones[1]/51 - ones[0]/140):+.2f}" == gap
for period, group, *cells in tables["c2transitions"]:
    pre, post = period.split("→")
    subset = long[long[high].eq(int(group == "고비중"))]
    counts = Counter(zip(subset[f"y{pre}"], subset[f"y{post}"]))
    assert cells[:4] == [counts[(a, b)] for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))]
    assert int(cells[4].replace("−", "-")) == counts[(0, 1)] - counts[(1, 0)]
for group, data in linked.groupby(high):
    assert data.y2025.notna().all() and data.y2026.notna().all()
    assert [int(data.y2025.sum()), int(data.y2026.sum())] == ([35, 35] if group else [70, 93])
assert f"{-100*23/195:.2f}" == "-11.79"
binary = wide[~wide.code.isin(["0180", "1480"])]
gaps = {}
for year, comparison_cell, high_cell, gap_cell in tables["c2missing"]:
    bounds = {}
    for group, data in binary.groupby(high):
        values = data[f"y{year}"]
        lower = 100 * values.sum() / len(values)
        upper = 100 * (values.sum() + values.isna().sum()) / len(values)
        bounds[group] = lower, upper
    lower = bounds[1][0] - bounds[0][1]
    upper = bounds[1][1] - bounds[0][0]
    for group, cell in [(0, comparison_cell), (1, high_cell)]:
        assert cell == "–".join(f"{value:.2f}" for value in bounds[group])
    expected_gap = f"{lower:+.2f}–{upper:+.2f}".replace("-", "−")
    assert gap_cell == expected_gap, (year, gap_cell, expected_gap)
    gaps[year] = lower, upper
assert gaps[2025][0] > gaps[2026][1]
assert gaps[2026][0] < 0 < gaps[2026][1]

audit = pd.read_csv(CASE2 / "results/second_audit_models.csv")
for row in tables["c2second"]:
    family = "fold_only" if row[0] == "폴드만 변경" else "learner_rng_only"
    data = audit[audit.family.eq(family) & audit.period.eq(row[1])]
    assert row[2] == f"[{data.estimate_pp.min():.2f}, {data.estimate_pp.max():.2f}]"
    assert row[3] == f"{data.p_value.lt(.05).sum()}/{len(data)}"
main = pd.read_csv(CASE2 / "results/dml_main.csv")
for row, record in zip(tables["c2new"], main.itertuples()):
    assert row[0] == record.period and row[2] == f"{record.estimate_pp:+.2f}"
    assert row[3] == f"[{record.lo_pp:.2f}, {record.hi_pp:.2f}]"
    assert row[4] == f"{record.p_value:.3f}"
print("Checked panel structure, four cross-sectional fits, four FE fits, VIND28 counts, DML and split sensitivity tables.")
