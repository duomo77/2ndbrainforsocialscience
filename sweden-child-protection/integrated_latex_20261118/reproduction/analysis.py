"""Independent, documented DML-DID reconstruction; NOT the recovered original code.

Score: DoubleML observational panel DID, in-sample normalization.
https://docs.doubleml.org/stable/guide/scores.html#difference-in-differences-models
No post-outcome selection of learners, seeds or hyperparameters.
"""
from pathlib import Path
import json,platform,sys,hashlib
import numpy as np,pandas as pd,scipy,sklearn
from scipy.stats import t
from sklearn.ensemble import RandomForestClassifier,RandomForestRegressor,ExtraTreesClassifier,ExtraTreesRegressor
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss,mean_squared_error
from fetch import P
FEATURES=['log_population_2015','elderly_pct_2015','female_pct_2015','median_income_2015','poverty_pct_2015']
SEED=20261106
def models(kind,seed):
 if kind=='linear':return make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=2000)),make_pipeline(StandardScaler(),Ridge(alpha=1))
 cls,reg=(RandomForestClassifier,RandomForestRegressor) if kind=='rf' else (ExtraTreesClassifier,ExtraTreesRegressor)
 return cls(n_estimators=300,min_samples_leaf=8,max_features=1.0,random_state=seed,n_jobs=1),reg(n_estimators=300,min_samples_leaf=8,max_features=1.0,random_state=seed,n_jobs=1)
def fold_ids(groups,seed):
 # Shuffle the 21 county labels once, split into 5 disjoint county sets (5,4,4,4,4).
 counties=np.array(sorted(set(groups)));np.random.default_rng(seed).shuffle(counties)
 mapping={g:k for k,chunk in enumerate(np.array_split(counties,5)) for g in chunk}
 return np.array([mapping[g] for g in groups])
def infer(phi,groups,theta):
 n=len(phi);cs=pd.Series(phi).groupby(np.asarray(groups)).sum();G=len(cs)
 se=np.sqrt(G/(G-1)*np.sum(cs.to_numpy()**2)/n**2)
 cv=t.ppf(.975,G-1);p=2*t.sf(abs(theta/se),G-1) if se else np.nan
 return dict(estimate_pp=theta*100,se_pp=se*100,lo_pp=(theta-cv*se)*100,hi_pp=(theta+cv*se)*100,p_value=p,n=n,counties=G)
def score(d,y,p,g,groups):
 pi=d.mean();w=(1-d)*p/(1-p);r=y-g
 theta=np.mean((d/pi-w/w.mean())*r)
 phi=-d/pi*theta+(d/pi-w/w.mean())*r
 assert abs(phi.mean())<1e-12
 out=infer(phi,groups,theta)
 out.update(control_ess=w.sum()**2/(w@w),ps_min=p.min(),ps_max=p.max(),max_normalized_control_weight=(w/w.sum()).max())
 return out,phi,w
def fit(df,pre,post,kind='rf',seed=SEED,clip=.05,save=False,income='DispInkInkl'):
 a=df.copy();a['median_income_2015']=a['median_'+income];a['poverty_pct_2015']=a['poverty_'+income]
 X=a[FEATURES].to_numpy(float);d=a.high_foreign_2015.to_numpy(float);groups=a.county.to_numpy();fold=fold_ids(groups,seed)
 assert np.isfinite(X).all()
 dy=a['y'+str(post)].to_numpy()-a['y'+str(pre)].to_numpy();predp=np.empty(len(a));predg=np.empty(len(a))
 audit=[]
 for k in range(5):
  test=fold==k;train=~test;control=train&(d==0)
  assert not set(groups[test])&set(groups[train]);assert len(set(d[train]))==2
  c,r=models(kind,seed+k);c.fit(X[train],d[train]);r.fit(X[control],dy[control])
  predp[test]=c.predict_proba(X[test])[:,1];predg[test]=r.predict(X[test])
  audit.append(dict(fold=k,test_counties=sorted(set(groups[test])),train_counties=sorted(set(groups[train])),test_n=int(test.sum()),train_control_n=int(control.sum())))
 clipped=np.clip(predp,clip,1-clip);result,phi,w=score(d,dy,clipped,predg,groups)
 result.update(period=f'{post}-{pre}',method='DML-DID',learner=kind,seed=seed,clip=clip,income=income,clipped_n=int((clipped!=predp).sum()),ps_brier=brier_score_loss(d,predp),control_change_rmse=float(np.sqrt(mean_squared_error(dy[d==0],predg[d==0]))))
 if save:
  o=a[['code','county','high_foreign_2015']].copy();o['fold']=fold;o['delta_y']=dy;o['ps_raw']=predp;o['ps_clipped']=clipped;o['g0_oof']=predg;o['influence']=phi;o['control_weight']=w/w.sum()
  o.to_csv(P/'results'/f'oof_{post}_{pre}.csv',index=False)
  (P/'results'/f'folds_{post}_{pre}.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 return result
def run():
 b=pd.read_csv(P/'data/municipality_analysis_wide.csv',dtype={'code':str,'county':str});a=b[b.long_panel].copy()
 assert len(a)==191 and a.high_foreign_2015.sum()==51 and a.county.nunique()==21
 periods=[(2023,2025),(2023,2026),(2025,2026)]
 main=[];sensitivity=[];unadjusted=[]
 for pre,post in periods:
  y=(a['y'+str(post)]-a['y'+str(pre)]).to_numpy();d=a.high_foreign_2015.to_numpy();p=d.mean();theta=y[d==1].mean()-y[d==0].mean()
  phi=d/p*(y-y[d==1].mean())-(1-d)/(1-p)*(y-y[d==0].mean())
  u=infer(phi,a.county,theta);u.update(period=f'{post}-{pre}',method='Unadjusted-DID');unadjusted.append(u)
  # Constant propensity and control-change model must collapse to the simple DID.
  test,_,_=score(d,y,np.full(len(d),p),np.full(len(d),y[d==0].mean()),a.county)
  assert abs(test['estimate_pp']-u['estimate_pp'])<1e-10 and abs(test['se_pp']-u['se_pp'])<1e-10
  main.append(fit(a,pre,post,save=True))
  print('MAIN',json.dumps(main[-1]),flush=True)
  for kind in ['linear','extra']:
   sensitivity.append(fit(a,pre,post,kind=kind))
  for seed in [20261107,20261108,20261109,20261110]:sensitivity.append(fit(a,pre,post,seed=seed))
  for clip in [.01,.10]:sensitivity.append(fit(a,pre,post,clip=clip))
  sensitivity.append(fit(a,pre,post,income='DispInkExkl'))
 pd.DataFrame(main).to_csv(P/'results/dml_main.csv',index=False)
 pd.DataFrame(sensitivity).to_csv(P/'results/dml_sensitivity.csv',index=False)
 pd.DataFrame(unadjusted).to_csv(P/'results/unadjusted_did.csv',index=False)
 refs={'2025-2023':(18.10,1.81,34.39),'2026-2023':(-8.36,-25.68,8.96),'2026-2025':(-26.46,-44.38,-8.54)}
 comparison=[]
 for r in main:
  v=refs[r['period']];comparison.append(dict(period=r['period'],reported_pp=v[0],reported_lo=v[1],reported_hi=v[2],new_pp=r['estimate_pp'],new_lo=r['lo_pp'],new_hi=r['hi_pp'],difference_pp=r['estimate_pp']-v[0],exact_replication=False))
 pd.DataFrame(comparison).to_csv(P/'results/reported_vs_reestimated.csv',index=False)
 # Annual transition cells are recovered from linked municipality records.
 trans=[]
 for sample,frame in [('long191',a),('linked263',b[b.linked_2025_2026])]:
  for high,g in frame.groupby('high_foreign_2015'):
   row=dict(sample=sample,high=int(high),n=len(g),yes2025=int(g.y2025.sum()),yes2026=int(g.y2026.sum()))
   for y0 in [0,1]:
    for y1 in [0,1]:row[f'n{y0}{y1}']=int(((g.y2025==y0)&(g.y2026==y1)).sum())
   trans.append(row)
 pd.DataFrame(trans).to_csv(P/'results/transitions.csv',index=False)
 env=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,system=platform.platform(),features=FEATURES,main_seed=SEED,main_clip=.05,learner='RandomForestClassifier/Regressor 300 trees, min_samples_leaf=8, max_features=1.0; seed+k per fold',standard_errors='County-clustered orthogonal-score influence sums; G/(G-1); t(G-1); no municipality independent SE',code_origin='New independent reconstruction: original executable code not located',tests=['191 observations/51 high/21 counties','No county leakage across folds','Finite observed covariates, no imputation','Zero mean estimating score','Constant nuisance score equals unadjusted DID estimate and SE'])
 (P/'results/environment.json').write_text(json.dumps(env,ensure_ascii=False,indent=2),encoding='utf-8')
 print('DONE',flush=True)
if __name__=='__main__':run()
