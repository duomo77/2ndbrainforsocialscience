"""Additional exploratory checks using downloaded, unmodified official-derived data.
Run: python upgrade_analysis.py. No network access and no missing-data imputation.
"""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import t

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)
XNAME='two_foreign_parents_among_Sweden_born'
d=pd.read_csv(ROOT/'data/metro_51_panel.csv',dtype={'municipality_code':str})
d['x_pp']=100*d[XNAME]
rows=[]

def sample(frame,x):
    frame=frame.dropna(subset=['U33401_days',x]).copy()
    counts=frame.groupby('municipality_code').size()
    return frame[frame.municipality_code.isin(counts[counts.ge(2)].index)].copy()

def fit(frame,x,spec):
    frame=sample(frame,x)
    model=smf.ols(f'U33401_days ~ {x} + C(municipality_code) + C(year)',frame)
    assert np.linalg.matrix_rank(model.exog)==model.exog.shape[1]
    result=model.fit(cov_type='cluster',cov_kwds={'groups':frame.municipality_code,'use_correction':True},use_t=True)
    ci=result.conf_int().loc[x]
    row=dict(specification=spec,predictor=x,n=len(frame),n_municipalities=frame.municipality_code.nunique(),
             coefficient=result.params[x],std_error=result.bse[x],p_value=result.pvalues[x],ci95_low=ci.iloc[0],ci95_high=ci.iloc[1])
    rows.append(row)
    return frame,model,result

base,model,result=fit(d[d.year.le(2024)],'x_pp','contemporaneous_2022_2024')
assert len(base)==126 and np.isclose(result.params['x_pp'],6.696774,atol=1e-6)
# Align by exact municipality/year keys, never carry observations across gaps.
lag=d[['municipality_code','year','x_pp']].copy()
lag['year']+=1;lag=lag.rename(columns={'x_pp':'lag_x_pp'})
aligned=d.merge(lag,on=['municipality_code','year'],how='left',validate='one_to_one')
fit(aligned[aligned.year.isin([2023,2024])],'lag_x_pp','lagged_population_2023_2024')
fit(aligned[aligned.year.isin([2023,2024])],'x_pp','same_outcome_window_contemporaneous_2023_2024')
# Fair timing comparison: both predictors observed and identical municipality-years.
common=aligned[aligned.year.isin([2023,2024])].dropna(subset=['x_pp','lag_x_pp','U33401_days'])
fit(common,'lag_x_pp','common_sample_lagged_2023_2024')
fit(common,'x_pp','common_sample_contemporaneous_2023_2024')
pd.DataFrame(rows).to_csv(OUT/'upgrade_timing_models.csv',index=False,encoding='utf-8-sig')

# Null-imposed wild cluster bootstrap-t, Rademacher weights, fixed design.
# Refit all nuisance fixed effects in every draw; recompute CR1 studentization.
X=model.exog;y=model.endog;pos=model.exog_names.index('x_pp')
Z=np.delete(X,pos,axis=1);restricted=Z@np.linalg.lstsq(Z,y,rcond=None)[0]
u0=y-restricted;bread=np.linalg.inv(X.T@X);projection=bread@X.T
codes=base.municipality_code.to_numpy(); unique=np.unique(codes)
members=[np.flatnonzero(codes==g) for g in unique]
G=len(unique);N,K=X.shape;factor=G/(G-1)*(N-1)/(N-K)
observed=result.tvalues['x_pp'];rng=np.random.default_rng(20261113)
B=9999;boot=[]
for start in range(0,B,250):
    count=min(250,B-start); signs=rng.choice([-1.,1.],size=(G,count))
    w=np.empty((N,count))
    for j,idx in enumerate(members):w[idx,:]=signs[j,:]
    ys=restricted[:,None]+u0[:,None]*w
    betas=projection@ys;errors=ys-X@betas
    variance=np.zeros(count)
    for idx in members:
        scores=X[idx].T@errors[idx]
        variance+=(bread[pos]@scores)**2
    boot.extend((betas[pos]/np.sqrt(factor*variance)).tolist())
boot=np.asarray(boot);exceed=int((abs(boot)>=abs(observed)).sum())
p=(exceed+1)/(B+1)
report=dict(method='Null-imposed wild cluster bootstrap-t, Rademacher, CR1 studentization',
            draws=B,seed=20261113,clusters=G,observed_t=float(observed),p_value=p,
            monte_carlo_se=float(np.sqrt(p*(1-p)/B)),exceedances=exceed,
            limitations='Exploratory two-sided test of zero slope only; no bootstrap confidence interval. Assumes independent municipality clusters; does not fix confounding or influential support.')
(OUT/'upgrade_wild_cluster_bootstrap.json').write_text(json.dumps(report,indent=2))

# Exact endpoint ratio decomposition: Δ(B/S)=mean(1/S)ΔB+mean(B)Δ(1/S).
pair=d[d.year.isin([2022,2024])].pivot(index=['municipality_code','municipality','metro'],columns='year',values=['B_sweden_born_two_foreign_parents','sweden_born_children_0_17','x_pp'])
out=pair.index.to_frame(index=False)
b0=pair['B_sweden_born_two_foreign_parents'][2022].to_numpy();b1=pair['B_sweden_born_two_foreign_parents'][2024].to_numpy()
s0=pair['sweden_born_children_0_17'][2022].to_numpy();s1=pair['sweden_born_children_0_17'][2024].to_numpy()
out['B_2022']=b0;out['B_2024']=b1;out['S_2022']=s0;out['S_2024']=s1
out['change_pp']=100*(b1/s1-b0/s0)
out['numerator_component_pp']=100*.5*(1/s0+1/s1)*(b1-b0)
out['denominator_component_pp']=100*.5*(b0+b1)*(1/s1-1/s0)
assert np.allclose(out.change_pp,out.numerator_component_pp+out.denominator_component_pp,atol=1e-10)
out.to_csv(OUT/'upgrade_ratio_decomposition.csv',index=False,encoding='utf-8-sig')

# Independent checks of the bootstrap covariance formula on the observed fit.
errors=result.resid.to_numpy();scores=np.vstack([X[idx].T@errors[idx] for idx in members])
cov=factor*bread@scores.T@scores@bread
assert np.isclose(np.sqrt(cov[pos,pos]),result.bse['x_pp'],rtol=1e-9)
assert np.isfinite(boot).all() and len(boot)==B and 0<p<=1
same=rows[-2:];assert same[0]['n']==same[1]['n'] and same[0]['n_municipalities']==same[1]['n_municipalities']
verification=dict(primary_reproduced=True,bootstrap_covariance_independently_matched=True,
                 exact_decomposition_all_51=True,lag_merge_one_to_one=True,common_timing_sample_matched=True,
                 input_sha256=hashlib.sha256((ROOT/'data/metro_51_panel.csv').read_bytes()).hexdigest())
(OUT/'upgrade_validation.json').write_text(json.dumps(verification,indent=2))
print(pd.DataFrame(rows).to_string(index=False));print(json.dumps(report,indent=2))
