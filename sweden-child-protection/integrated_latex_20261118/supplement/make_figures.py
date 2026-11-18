"""Create the supplement from the archived official data and fitted results."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker
from matplotlib.collections import PatchCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as DrawingPath
import numpy as np
import pandas as pd
import shapefile
import statsmodels.formula.api as smf

SUP = Path(__file__).resolve().parent
ROOT = SUP.parent
RAW = SUP / "raw"
OUT = SUP / "figures"
DATA = SUP / "data"
OUT.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)
RESULTS = ROOT / "reproduction/results"
FONT = next((font for font in ["Malgun Gothic", "Noto Sans CJK KR", "NanumGothic"]
             if font in {entry.name for entry in font_manager.fontManager.ttflist}), None)
if FONT is None:
    raise RuntimeError("Install Malgun Gothic, Noto Sans CJK KR, or NanumGothic.")
plt.rcParams.update({"font.family": FONT, "axes.unicode_minus": False, "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.labelcolor": "#263746", "text.color": "#183044",
                     "xtick.color": "#344a5a", "ytick.color": "#344a5a",
                     "figure.facecolor": "white", "savefig.facecolor": "white"})
BLUE = "#126e89"
ORANGE = "#a84225"
SLATE = "#657782"
NO_VALUE = "#e3e6e9"
CONTEXT = "#f3f4f5"

def save(fig, name):
    fig.savefig(OUT / (name + ".png"), dpi=210, bbox_inches="tight", pad_inches=.08)
    plt.close(fig)

def load_boundaries():
    with ZipFile(RAW / "scb_boundaries.zip") as outer:
        with ZipFile(BytesIO(outer.read("Kommun_Sweref99TM.zip"))) as inner:
            stem = "Kommun_Sweref99TM"
            reader = shapefile.Reader(shp=BytesIO(inner.read(stem + ".shp")),
                                      dbf=BytesIO(inner.read(stem + ".dbf")), encoding="cp1252")
            shapes = {}
            for item in reader.iterShapeRecords():
                code, name = item.record
                assert code not in shapes and len(code) == 4 and code.isdecimal()
                starts = [*item.shape.parts, len(item.shape.points)]
                rings = [np.asarray(item.shape.points[a:b]) for a,b in zip(starts, starts[1:])]
                shapes[code] = (name, item.shape.bbox, rings)
            return shapes

def total_kolada(year, codes):
    response = json.loads((RAW / f"kolada_N02926_{year}.json").read_bytes())
    assert response["next_url"] is None
    out = {}
    for item in response["values"]:
        code = item["municipality"]
        if code not in codes:
            continue
        assert item["kpi"] == "N02926" and item["period"] == year and code not in out
        total, = [row for row in item["values"] if row["gender"] == "T"]
        assert total["isdeleted"] is False and total["status"] == ""
        out[code] = float(total["value"])
    assert set(out) == codes and all(0 <= value <= 100 for value in out.values())
    return pd.Series(out, dtype=float)

def scale(edges, palette):
    return ListedColormap(palette), BoundaryNorm(edges, len(palette))

SHARES = [0, 10, 15, 20, 25, 30, 40, 60]
SHARE_SCALE = scale(SHARES, ["#eff5fb", "#d6e7f2", "#b4d4e5", "#80b9d6",
                             "#4b94be", "#256fa2", "#124772"])
BACK = [0, 10, 20, 30, 40, 50, 60, 100]
BACK_SCALE = scale(BACK, ["#f1edf7", "#e2d8ec", "#cdbbdf", "#b096cb",
                         "#9372b5", "#744b98", "#522a78"])
DAYS = [60, 80, 90, 100, 110, 120, 140]
DAY_SCALE = scale(DAYS, ["#fff6dc", "#fbe5b0", "#f8cc83", "#eea452", "#d9772e", "#a7481f"])

def legend(ax, edges, color_key, unit, missing=False):
    cmap, _ = color_key
    handles = [Patch(facecolor=cmap(i), edgecolor="none", label=f"{a}–{b}")
               for i, (a, b) in enumerate(zip(edges, edges[1:]))]
    if missing:
        handles.append(Patch(facecolor=NO_VALUE, edgecolor=SLATE, hatch="///", label="미관측"))
    ax.axis("off")
    ax.legend(handles=handles, ncol=len(handles), loc="center", frameon=False,
              title=unit, fontsize=8.5, title_fontsize=9.5, columnspacing=.75,
              handlelength=1.05, handletextpad=.35, borderaxespad=0)

def patches_for(rings):
    paths = [DrawingPath(ring, closed=True) for ring in rings if len(ring) >= 4]
    return PathPatch(DrawingPath.make_compound_path(*paths))

def shape_map(ax, shapes, values, color_key, focus=None):
    cmap, norm = color_key
    selected = set(shapes) if focus is None else set(focus)
    focus_boxes = np.asarray([shapes[code][1] for code in selected])
    west, south = focus_boxes[:, :2].min(axis=0)
    east, north = focus_boxes[:, 2:].max(axis=0)
    pad = max(east-west, north-south)*.03
    regular, colors, missing = [], [], []
    for code, (_, bbox, rings) in shapes.items():
        if bbox[2] < west-pad or bbox[0] > east+pad or bbox[3] < south-pad or bbox[1] > north+pad:
            continue
        value = values.get(code, np.nan)
        patch = patches_for(rings)
        if code in selected and pd.isna(value):
            missing.append(patch)
        else:
            regular.append(patch)
            colors.append(cmap(norm(value)) if code in selected else CONTEXT)
    ax.add_collection(PatchCollection(regular, facecolors=colors, edgecolor="white", linewidth=.35))
    if missing:
        ax.add_collection(PatchCollection(missing, facecolor=NO_VALUE, edgecolor="#78858f",
                                          linewidth=.4, hatch="///"))
    ax.set(xlim=(west-pad,east+pad), ylim=(south-pad,north+pad), aspect="equal")
    ax.axis("off")

def national_maps(shapes, values):
    fig = plt.figure(figsize=(7.1, 6.6), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=[12, 1.18])
    for i, year in enumerate([2015, 2024]):
        ax = fig.add_subplot(grid[0, i])
        shape_map(ax, shapes, values[f"foreign_born_pct_{year}"], SHARE_SCALE)
        ax.set_title(str(year)+"년", loc="center", weight="bold", pad=7)
    legend(fig.add_subplot(grid[1, :]), SHARES, SHARE_SCALE, "해외 출생 주민 비중 (%)")
    save(fig, "s1_sweden_foreign_born")

def metro_maps(shapes, panel):
    fig = plt.figure(figsize=(9.0, 8.2), layout="constrained")
    grid = fig.add_gridspec(4, 3, height_ratios=[4, 4, 4, 1.22])
    region_names = [("0010", "스톡홀름권", 26), ("0020", "예테보리권", 13), ("0030", "말뫼권", 12)]
    columns = [("N02926_pct", "해외 출생 주민 (%)", SHARES, SHARE_SCALE),
               ("child_background_pct", "해외 배경 아동 (%)", BACK, BACK_SCALE),
               ("U33401_days", "조사기간 (일)", DAYS, DAY_SCALE)]
    for i, (code, region, n) in enumerate(region_names):
        subset = panel[panel.metro_code.eq(code)]
        assert len(subset) == n
        for j, (column, title, edges, colors) in enumerate(columns):
            ax = fig.add_subplot(grid[i, j])
            shape_map(ax, shapes, subset[column], colors, focus=subset.index)
            ax.set_title(f"{region} · {title}", fontsize=10.5, weight="bold", pad=2)
    for j, (column, title, edges, colors) in enumerate(columns):
        ax = fig.add_subplot(grid[3, j]); ax.axis("off")
        handles = [Patch(facecolor=colors[0](i), label=f"{a}–{b}")
                   for i,(a,b) in enumerate(zip(edges,edges[1:]))]
        if column == "U33401_days":
            handles.append(Patch(facecolor=NO_VALUE, edgecolor=SLATE, hatch="///", label="미관측"))
        ax.legend(handles=handles, ncol=3, loc="upper center", frameon=False, fontsize=8.1,
                  columnspacing=.60, handlelength=1.05, handletextpad=.28)
    save(fig, "s2_metro_maps")

def metro_fits(panel):
    panel = panel.reset_index().rename(columns={"index": "municipality_code"})
    panel = panel[panel.year.isin([2022, 2023, 2024])].dropna(subset=["U33401_days"]).copy()
    group_n = panel.groupby("municipality_code").year.transform("size")
    panel = panel[group_n.eq(3)].assign(x=lambda d: 100*d.two_foreign_parents_among_Sweden_born)
    assert (len(panel), panel.municipality_code.nunique()) == (120, 40)
    cross = panel[panel.year.eq(2024)].copy()
    specifications = [(cross, "C(metro)", "2024년 지역 간 비교"),
                      (panel, "C(municipality_code)+C(year)", "2022–2024년 지역 내 비교")]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), layout="constrained")
    rows = []
    for ax,(frame, rhs, title), expected in zip(axes, specifications, [-.105, 6.555]):
        x = smf.ols("x ~ "+rhs, frame).fit().resid
        y = smf.ols("U33401_days ~ "+rhs, frame).fit().resid
        coef = float(x @ y / (x @ x))
        assert abs(coef-expected)<.001
        ax.scatter(x, y, color=BLUE, s=22, alpha=.62, edgecolors="white", linewidth=.42)
        xx = np.array([x.min(), x.max()])
        ax.plot(xx, coef*xx, color=ORANGE, lw=1.6)
        ax.axhline(0, color="#cad3d9", lw=.8, zorder=0)
        ax.set(title=title, xlabel="양부모 해외 출생 비중 잔차 (%p)", ylabel="조사기간 잔차 (일)")
        ax.text(.03,.96,f"기울기 {coef:+.3f} 일/%p", transform=ax.transAxes, va="top",
                fontsize=9.5, bbox=dict(facecolor="white", edgecolor="none", alpha=.93))
        rows.append(frame[["municipality_code","year"]].assign(comparison=title,x_residual=x,y_residual=y))
    pd.concat(rows).to_csv(DATA/"metro_partial_residuals.csv", index=False, encoding="utf-8-sig")
    save(fig,"s3_metro_partial_residuals")

def vind_levels(vind):
    years = [2018,2019,2020,2021,2022,2023,2025,2026]
    cols = ["y"+str(y) for y in years]
    samples = [("장기패널 · 191개",vind[vind.long_panel],years),
               ("최근 연결표본 · 263개",vind[vind.linked_2025_2026],[2025,2026])]
    fig,axes = plt.subplots(1,2,figsize=(8.7,3.55),sharey=True,
                           gridspec_kw={"width_ratios":[2.7,1]},layout="constrained")
    rows = []
    for ax,(label,frame,ys) in zip(axes,samples):
        for group, color, marker, name in [(1,BLUE,"o","고비중 집단"),(0,ORANGE,"s","비교집단")]:
            sub = frame[frame.high_foreign_2015.eq(group)]
            pct = 100*sub[["y"+str(y) for y in ys]].mean().to_numpy()
            ax.plot(ys,pct,ls="--",color=color,lw=1.7,marker=marker,ms=5,label=name)
            counts = sub[["y"+str(y) for y in ys]].sum().to_numpy()
            rows.extend(dict(sample=label,group=group,year=y,n=len(sub),yes=int(count),rate_pct=v)
                        for y,count,v in zip(ys,counts,pct))
        ax.set(title=label,ylim=(0,70),xticks=ys)
        ax.grid(axis="y",color="#e3e8ec",lw=.7); ax.set_axisbelow(True)
        ax.tick_params(axis="x",labelsize=8.5)
    axes[0].set_ylabel("학업보장 절차 충족률 (%)")
    axes[0].axvline(2024,color="#8a9197",lw=.85,alpha=.75)
    axes[0].text(2024,67,"2024년 제도 개편",ha="center",va="top",fontsize=8.5,color=SLATE)
    axes[1].legend(frameon=False,loc="lower left",fontsize=9)
    pd.DataFrame(rows).to_csv(DATA/"vind_levels.csv",index=False,encoding="utf-8-sig")
    save(fig,"s4_vind28_levels")

def split_plot():
    audit = pd.read_csv(RESULTS/"second_audit_models.csv")
    legacy = pd.read_csv(RESULTS/"reported_vs_reestimated.csv").set_index("period")
    main = pd.read_csv(RESULTS/"dml_main.csv").set_index("period")
    periods = ["2025-2023","2026-2023","2026-2025"]
    fig,axs = plt.subplots(1,3,figsize=(8.7,4.5),sharey=True,layout="constrained")
    for ax,period in zip(axs,periods):
        points = audit[audit.family.eq("fold_only") & audit.period.eq(period)].sort_values("fold_seed")
        assert len(points)==10
        ax.axhline(0,color="#78858f",lw=.8)
        ax.scatter(np.linspace(.80,1.20,10), points.estimate_pp, c=SLATE, s=20, alpha=.8)
        for x, table, prefix, color, marker in [(0,main,"",BLUE,"o"),(2,legacy,"reported_",ORANGE,"s")]:
            row=table.loc[period]
            center=row["estimate_pp" if x==0 else "reported_pp"]
            low=row[prefix+"lo_pp" if x==0 else "reported_lo"]
            high=row[prefix+"hi_pp" if x==0 else "reported_hi"]
            ax.errorbar(x,center,yerr=[[center-low],[high-center]],color=color,marker=marker,
                        ms=5,capsize=4,lw=1.4,zorder=3)
        ax.set(title=period.replace("-"," 대 "),xlim=(-.4,2.40),xticks=[0,1,2],
               xticklabels=["독립\n주 추정","폴드만\n변경","기존\n보고치"],ylim=(-50,40))
        ax.grid(axis="y",color="#e3e8ec",lw=.7); ax.set_axisbelow(True)
        ax.tick_params(axis="x",labelsize=9)
    axs[0].set_ylabel("조정 변화 차이 (%p)")
    save(fig,"s5_vind28_dml_folds")

shapes=load_boundaries()
assert len(shapes)==290
pop=pd.DataFrame({f"foreign_born_pct_{year}":total_kolada(year,set(shapes)) for year in [2015,2024]})
pop.index.name="municipality_code"
pop.insert(0,"municipality",[shapes[code][0] for code in pop.index])
annual=pd.read_csv(ROOT/"data/metro_51_2024.csv",dtype={"municipality_code":str,"metro_code":str}).set_index("municipality_code")
assert len(annual)==51 and annual.U33401_days.count()==44 and set(annual.index)<=set(pop.index)
np.testing.assert_allclose(pop.loc[annual.index,"foreign_born_pct_2024"],annual.N02926_pct_2024 if "N02926_pct_2024" in annual else annual.N02926_pct,atol=1e-8)
annual["child_background_pct"]=100*annual.foreign_background
pop.to_csv(DATA/"sweden_map_values.csv",encoding="utf-8-sig")
annual[["metro_code","N02926_pct","child_background_pct","U33401_days"]].to_csv(DATA/"metro_map_values.csv",encoding="utf-8-sig")
panel=pd.read_csv(ROOT/"data/metro_51_panel.csv",dtype={"municipality_code":str}).set_index("municipality_code")
vind=pd.read_csv(ROOT/"reproduction/data/municipality_analysis_wide.csv",dtype={"code":str})
assert set(vind.code)==set(pop.index)
national_maps(shapes,pop)
metro_maps(shapes,annual)
metro_fits(panel)
vind_levels(vind)
split_plot()
audit_info={"boundary_codes":len(shapes),"map_2015_observed":int(pop.foreign_born_pct_2015.count()),
            "map_2024_observed":int(pop.foreign_born_pct_2024.count()),
            "metro_included":len(annual),"metro_duration_observed":int(annual.U33401_days.count()),
            "raw_sha256":{p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.iterdir()) if p.is_file()}}
(DATA/"map_validation.json").write_text(json.dumps(audit_info,indent=2),encoding="utf-8")
print(json.dumps(audit_info,indent=2))
