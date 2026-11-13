"""Same-sample between/within comparison for the panel-results follow-up."""
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

root=Path(__file__).resolve().parent
d=pd.read_csv(root/'data/metro_51_panel.csv',dtype={'municipality_code':str})
d=d[d.year.le(2024)].dropna(subset=['U33401_days'])
n=d.groupby('municipality_code').size()
d=d[d.municipality_code.isin(n[n.eq(3)].index)].copy()
assert len(d)==120 and d.municipality_code.nunique()==40
rows=[]
terms=['C(municipality_code)','C(year)']
for j,metro in enumerate(sorted(d.metro.unique())[1:]):
    for year in [2023,2024]:
        name=f'metro_year_{j}_{year}'
        d[name]=((d.metro==metro)&(d.year==year)).astype(float)
        terms.append(name)
for x in ['foreign_born_share','foreign_background','any_foreign_parent_among_Sweden_born','two_foreign_parents_among_Sweden_born']:
    d['x_pp']=d[x]*100
    c=d[d.year.eq(2024)].copy()
    cross=smf.ols('U33401_days ~ x_pp + C(metro)',c).fit(cov_type='HC3',use_t=True)
    panel=smf.ols('U33401_days ~ x_pp + C(municipality_code) + C(year)',d).fit(
        cov_type='cluster',cov_kwds={'groups':d.municipality_code,'use_correction':True},use_t=True)
    residual=smf.ols('x_pp ~ C(municipality_code) + C(year)',d).fit().resid
    joint_model=smf.ols('U33401_days ~ x_pp + '+' + '.join(terms),d)
    assert np.linalg.matrix_rank(joint_model.exog)==joint_model.exog.shape[1]
    joint=joint_model.fit(cov_type='cluster',cov_kwds={'groups':d.municipality_code,'use_correction':True},use_t=True)
    # Independent matrix calculation of the clustered covariance, including correction.
    X=joint_model.exog; y=joint_model.endog
    bread=np.linalg.inv(X.T@X); beta=bread@X.T@y
    error=y-X@beta
    scores=np.vstack([X[d.municipality_code.eq(code)].T@error[d.municipality_code.eq(code)]
                      for code in d.municipality_code.unique()])
    G=d.municipality_code.nunique(); N,K=X.shape
    cov=(G/(G-1))*((N-1)/(N-K))*bread@(scores.T@scores)@bread
    pos=joint_model.exog_names.index('x_pp')
    assert np.isclose(beta[pos],joint.params['x_pp'],rtol=1e-8,atol=1e-8)
    assert np.isclose(np.sqrt(cov[pos,pos]),joint.bse['x_pp'],rtol=1e-8,atol=1e-8)
    ci=joint.conf_int().loc['x_pp']
    rows.append(dict(predictor=x,municipalities=40,cross2024_beta=cross.params['x_pp'],
                     cross2024_p=cross.pvalues['x_pp'],panel_beta=panel.params['x_pp'],
                     panel_p=panel.pvalues['x_pp'],two_way_residual_sd_pp=residual.std(),
                     balanced_metro_year_beta=joint.params['x_pp'],balanced_metro_year_se=joint.bse['x_pp'],
                     balanced_metro_year_p=joint.pvalues['x_pp'],balanced_metro_year_ci95_low=ci.iloc[0],
                     balanced_metro_year_ci95_high=ci.iloc[1]))
result=pd.DataFrame(rows)
result.to_csv(root/'results/panel_same_sample_comparison.csv',index=False,encoding='utf-8-sig')
print(result.to_string(index=False))
