"""Plot validated existing estimates alongside the additional timing checks."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
root=Path(__file__).resolve().parent
regs=pd.read_csv(root/'results/regressions.csv')
q='two_foreign_parents_among_Sweden_born'
regs=regs[regs.predictor.eq(q)]
print(regs[['specification','coefficient']].to_string(index=False))
cross=regs[regs.specification.eq('OLS_metro_FE') & regs['sample'].astype(str).eq('2024')].iloc[0]
levels=pd.read_csv(root/'results/two_parent_influence_models.csv')
fd=pd.read_csv(root/'results/two_parent_first_difference_models.csv')
timing=pd.read_csv(root/'results/upgrade_timing_models.csv')
items=[('2024 단면 대도시권 조정',cross),
       ('2022–2024 지방정부 및 연도 FE',levels[levels.specification.eq('TWFE_unbalanced')].iloc[0]),
       ('균형표본 및 대도시권별 연도 FE',levels[levels.specification.eq('municipality_metro_year_balanced')].iloc[0]),
       ('인접 연도 일차차분',fd[fd.specification.eq('FD_adjacent_unbalanced')].iloc[0]),
       ('2022–2024 양 끝 시점 차분',fd[fd.specification.eq('FD_endpoint_2022_2024_metro_controls')].iloc[0]),
       ('2023–2024 전년도 비중 FE',timing[timing.specification.eq('common_sample_lagged_2023_2024')].iloc[0])]
plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(8,5.1))
for j,(label,row) in enumerate(items):
    b=row.coefficient;lo=row.ci95_low;hi=row.ci95_high
    ax.errorbar(b,j,xerr=[[b-lo],[hi-b]],fmt='o',color='black',capsize=3,markersize=4)
ax.axvline(0,color='gray',linewidth=.8,linestyle='--')
ax.set_yticks(range(len(items)),[v[0] for v in items],fontsize=10)
ax.invert_yaxis();ax.set_xlabel('비중 1%포인트당 조사일수   점 추정치와 95% 신뢰구간',fontsize=10)
ax.spines[['top','right','left']].set_visible(False)
ax.grid(axis='x',alpha=.15);fig.tight_layout()
fig.savefig(root/'results/upgrade_specifications.png',dpi=220,bbox_inches='tight')
pd.DataFrame([dict(label=label,coefficient=r.coefficient,ci95_low=r.ci95_low,ci95_high=r.ci95_high) for label,r in items]).to_csv(root/'results/upgrade_figure_data.csv',index=False,encoding='utf-8-sig')
