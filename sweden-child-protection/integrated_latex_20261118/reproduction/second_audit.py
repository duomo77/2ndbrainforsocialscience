"""Second audit: isolate implementation changes; never tune to legacy estimates."""
import json
import numpy as np,pandas as pd
from scipy.stats import norm
from analysis import P,FEATURES,SEED,models,fold_ids,score,infer

b=pd.read_csv(P/'data/municipality_analysis_wide.csv',dtype={'code':str,'county':str});a=b[b.long_panel].reset_index(drop=True)
X=a[FEATURES].to_numpy(float);d=a.high_foreign_2015.to_numpy(float);groups=a.county.to_numpy();periods=[(2023,2025),(2023,2026),(2025,2026)]
def predictions(foldseed=SEED,learnerseed=SEED,pkind='rf',gkind='rf',levels=False):
 f=fold_ids(groups,foldseed);p=np.empty(len(a));g=np.empty((len(a),3))
 for k in range(5):
  te=f==k;tr=~te;co=tr&(d==0)
  assert not set(groups[te])&set(groups[tr])
  c,_=models(pkind,learnerseed+k);c.fit(X[tr],d[tr]);p[te]=c.predict_proba(X[te])[:,1]
  if levels:
   lev={}
   for y in [2023,2025,2026]:
    _,r=models(gkind,learnerseed+k);r.fit(X[co],a.loc[co,'y'+str(y)]);lev[y]=r.predict(X[te])
   for j,(pre,post) in enumerate(periods):g[te,j]=lev[post]-lev[pre]
  else:
   for j,(pre,post) in enumerate(periods):
    _,r=models(gkind,learnerseed+k);r.fit(X[co],a.loc[co,'y'+str(post)]-a.loc[co,'y'+str(pre)]);g[te,j]=r.predict(X[te])
 return np.clip(p,.05,.95),g,f
rows=[];parts=[]
def evaluate(tag,p,g,f,family='controlled',**meta):
 for j,(pre,post) in enumerate(periods):
  y=(a['y'+str(post)]-a['y'+str(pre)]).to_numpy();r,phi,w=score(d,y,p,g[:,j],groups)
  r.update(setting=tag,family=family,period=f'{post}-{pre}',**meta);rows.append(r)
  o=pd.DataFrame(dict(code=a.code,county=groups,fold=f,period=f'{post}-{pre}',setting=tag,ps=p,g0=g[:,j],influence=phi));parts.append(o)
 print(tag,flush=True)

p0,g0,f0=predictions();evaluate('baseline',p0,g0,f0)
old=pd.read_csv(P/'results/dml_main.csv')
assert np.allclose([r['estimate_pp'] for r in rows],old.estimate_pp,rtol=0,atol=1e-10)
# One nuisance function at a time: evaluate both hybrid learners using identical folds.
pl,gl,fl=predictions(pkind='linear',gkind='linear')
evaluate('propensity_only_linear',pl,g0,f0)
evaluate('outcome_only_linear',p0,gl,f0)
evaluate('both_linear',pl,gl,f0)
pv,gv,fv=predictions(levels=True);assert np.array_equal(p0,pv)
evaluate('outcome_levels_then_difference',p0,gv,f0)
assert abs(rows[-1]['estimate_pp']-(rows[-2]['estimate_pp']-rows[-3]['estimate_pp']))<1e-10
for seed in range(20261201,20261211):
 p,g,f=predictions(foldseed=seed);evaluate(f'fold_only_{seed}',p,g,f,family='fold_only',fold_seed=seed,learner_seed=SEED)
for seed in range(20261201,20261206):
 p,g,f=predictions(learnerseed=seed);evaluate(f'learner_rng_only_{seed}',p,g,f,family='learner_rng_only',fold_seed=SEED,learner_seed=seed)

# Fixed predictions: show how normalization and inference change the answer.
for j,(pre,post) in enumerate(periods):
 y=(a['y'+str(post)]-a['y'+str(pre)]).to_numpy();res=y-g0[:,j];pi=d.mean();w=(1-d)*p0/(1-p0)
 theta=np.mean((d/pi-w/pi)*res);phi=-d/pi*theta+(d/pi-w/pi)*res
 r=infer(phi,groups,theta);r.update(setting='unnormalized_control_weights',family='normalization',period=f'{post}-{pre}');rows.append(r)
 base=next(r for r in rows if r['setting']=='baseline' and r['period']==f'{post}-{pre}')
 _,phi,_=score(d,y,p0,g0[:,j],groups);iid_se=np.std(phi,ddof=1)/np.sqrt(len(a));r=dict(estimate_pp=base['estimate_pp'],se_pp=iid_se*100,lo_pp=base['estimate_pp']-norm.ppf(.975)*iid_se*100,hi_pp=base['estimate_pp']+norm.ppf(.975)*iid_se*100,p_value=2*norm.sf(abs(base['estimate_pp']/100/iid_se)),setting='iid_normal_diagnostic_only',family='inference',period=f'{post}-{pre}')
 rows.append(r)
 treated=(d*res).sum()/d.sum();control=(w*res).sum()/w.sum()
 ratio_phi=d/pi*(res-treated)-w/w.mean()*(res-control)
 r=infer(ratio_phi,groups,(treated-control));r.update(setting='finite_sample_ratio_IF',family='inference',period=f'{post}-{pre}');rows.append(r)

df=pd.DataFrame(rows);df.to_csv(P/'results/second_audit_models.csv',index=False)
pd.concat(parts,ignore_index=True).to_csv(P/'results/second_audit_oof.csv',index=False)
summ=[]
for (family,period),v in df[df.family.isin(['fold_only','learner_rng_only'])].groupby(['family','period']):
 summ.append(dict(family=family,period=period,n=len(v),minimum=v.estimate_pp.min(),maximum=v.estimate_pp.max(),median=v.estimate_pp.median(),significant=int((v.p_value<.05).sum())))
pd.DataFrame(summ).to_csv(P/'results/second_audit_summary.csv',index=False)
meta=dict(original_code_recovered=False,original_exact_replication=False,one_at_a_time=True,main_unchanged=True,fold_seeds=list(range(20261201,20261211)),learner_seeds=list(range(20261201,20261206)),fold_and_learner_rng_separated=True,normalization='Diagnostic unnormalized weights use global treatment mean for both group denominators; not the complete DoubleML no-normalization option with foldwise p',iid='Diagnostic only; county clustering is required for substantive inference',ratio_IF='Finite-sample ratio-linearization sensitivity; not claimed to be the unique correct IF when nuisances are estimated',selection='All prelisted settings retained; none selected for matching old estimates')
(P/'results/second_audit_settings.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(df[df.family.isin(['controlled','normalization','inference'])][['setting','period','estimate_pp','lo_pp','hi_pp','p_value']].round(4).to_string(index=False),flush=True)
print(pd.DataFrame(summ).to_string(index=False),flush=True)
