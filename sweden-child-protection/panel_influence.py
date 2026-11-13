"""Observed-data influence and first-difference checks for the two-parent share.

Run: python panel_influence.py
No downloads, imputation, randomization, or observation replacement.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'
X='two_foreign_parents_among_Sweden_born'
data=pd.read_csv(ROOT/'data/metro_51_panel.csv',dtype={'municipality_code':str,'metro_code':str})
data=data[data.year.le(2024)].dropna(subset=['U33401_days',X]).copy()
data['x_pp']=data[X]*100
size=data.groupby('municipality_code').size()
data=data[data.municipality_code.isin(size[size.ge(2)].index)].copy()
assert len(data)==126 and data.municipality_code.nunique()==43
balanced_codes=set(size[size.eq(3)].index)
models={
    'TWFE_unbalanced':(data,False),
    'TWFE_balanced':(data[data.municipality_code.isin(balanced_codes)].copy(),False),
    'municipality_metro_year_unbalanced':(data,True),
    'municipality_metro_year_balanced':(data[data.municipality_code.isin(balanced_codes)].copy(),True),
}
checks=[]

def check(name,condition):
    checks.append({'check':name,'passed':bool(condition)})
    assert condition,name

def save(df,name):
    df.to_csv(OUT/name,index=False,encoding='utf-8-sig',float_format='%.12g')

def verify_covariance(model,result,g,cluster=True):
    A=model.exog; y=model.endog; N,K=A.shape
    bread=np.linalg.inv(A.T@A); beta=bread@A.T@y; e=y-A@beta
    if cluster:
        scores=np.vstack([A[g.municipality_code.eq(code)].T@e[g.municipality_code.eq(code)]
                          for code in g.municipality_code.unique()])
        G=g.municipality_code.nunique()
        cov=(G/(G-1))*((N-1)/(N-K))*bread@(scores.T@scores)@bread
    else:
        h=np.sum((A@bread)*A,axis=1)
        cov=bread@(A.T@(((e/(1-h))**2)[:,None]*A))@bread
    pos=model.exog_names.index('x_pp')
    assert np.isclose(beta[pos],result.params['x_pp'],atol=1e-8,rtol=1e-8)
    assert np.isclose(np.sqrt(cov[pos,pos]),result.bse['x_pp'],atol=1e-8,rtol=1e-8)

def fit(g,metro=False):
    g=g.copy()
    n=g.groupby('municipality_code').size()
    g=g[g.municipality_code.isin(n[n.ge(2)].index)].copy()
    terms=['C(municipality_code)','C(year)']
    if metro:
        for j,m in enumerate(sorted(g.metro.unique())[1:]):
            for year in sorted(g.year.unique())[1:]:
                name=f'metro_year_{j}_{year}'
                g[name]=((g.metro==m)&(g.year==year)).astype(float)
                terms.append(name)
    model=smf.ols('U33401_days ~ x_pp + '+' + '.join(terms),g)
    assert np.linalg.matrix_rank(model.exog)==model.exog.shape[1]
    result=model.fit(cov_type='cluster',cov_kwds={'groups':g.municipality_code,'use_correction':True},use_t=True)
    verify_covariance(model,result,g)
    return result,g,terms

def summary(result,g,spec,kind='levels'):
    ci=result.conf_int().loc['x_pp']
    return dict(specification=spec,kind=kind,n=len(g),municipalities=g.municipality_code.nunique(),
                coefficient=result.params['x_pp'],std_error=result.bse['x_pp'],p_value=result.pvalues['x_pp'],
                ci95_low=ci.iloc[0],ci95_high=ci.iloc[1],unit='days per percentage point')

base_rows=[]; loo=[]; cells=[]; components=[]; groups=[]; cumulative=[]
for spec,(frame,metro) in models.items():
    res,g,terms=fit(frame,metro)
    base_rows.append(summary(res,g,spec))
    beta=res.params['x_pp']
    rx=smf.ols('x_pp ~ '+' + '.join(terms),g).fit().resid
    ry=smf.ols('U33401_days ~ '+' + '.join(terms),g).fit().resid
    denom=np.dot(rx,rx); numerator=np.dot(rx,ry)
    check('FWL equals original slope '+spec,np.isclose(numerator/denom,beta,atol=1e-9))
    c=g[['municipality_code','municipality','metro','year','x_pp','U33401_days']].copy()
    c['specification']=spec; c['residual_x_pp']=rx; c['residual_y_days']=ry
    c['covariance_numerator']=rx*ry; c['slope_contribution']=rx*ry/denom
    c['covariance_share']=rx*ry/numerator
    c['partial_x_information_share']=rx**2/denom
    components.append(c)
    agg=c.groupby(['municipality_code','municipality','metro'],as_index=False)[
        ['covariance_numerator','slope_contribution','covariance_share','partial_x_information_share']].sum()
    agg['specification']=spec
    local=[]
    for r in agg.itertuples():
        omitted=g[g.municipality_code.ne(r.municipality_code)]
        drop,sub,_=fit(omitted,metro)
        row=summary(drop,sub,spec)
        row.update(omitted_code=r.municipality_code,omitted_municipality=r.municipality,
                   full_coefficient=beta,change_after_omission=drop.params['x_pp']-beta,
                   supporting_influence=beta-drop.params['x_pp'])
        loo.append(row); local.append(row)
    l=pd.DataFrame(local)
    agg=agg.merge(l[['omitted_code','supporting_influence','coefficient','p_value']],
                  left_on='municipality_code',right_on='omitted_code',validate='one_to_one').drop(columns='omitted_code')
    agg=agg.rename(columns={'coefficient':'coefficient_omitting_municipality','p_value':'p_omitting_municipality'})
    groups.append(agg)
    # Fixed ranking from the full-sample leave-one-out slope changes. These are
    # deliberate stress tests, not prespecified samples or valid selection tests.
    ranked=l[l.supporting_influence.gt(0)].sort_values('supporting_influence',ascending=False)
    for k in range(1,min(5,len(ranked))+1):
        codes=ranked.head(k).omitted_code.tolist()
        drop,sub,_=fit(g[~g.municipality_code.isin(codes)],metro)
        row=summary(drop,sub,spec)
        row.update(omitted_count=k,omitted_codes=','.join(codes),
                   omitted_municipalities='; '.join(ranked.head(k).omitted_municipality))
        cumulative.append(row)
    # Exact cell-deletion checks for the original primary model and strongest control sensitivity.
    if spec in ['TWFE_unbalanced','municipality_metro_year_balanced']:
        for idx,r in g.iterrows():
            drop,sub,_=fit(g.drop(index=idx),metro)
            row=summary(drop,sub,spec)
            row.update(omitted_code=r.municipality_code,omitted_municipality=r.municipality,
                       omitted_year=int(r.year),full_coefficient=beta,
                       supporting_influence=beta-drop.params['x_pp'],actual_rows_removed=len(g)-len(sub))
            cells.append(row)
        ranked_cells=pd.DataFrame(cells)
        ranked_cells=ranked_cells[ranked_cells.specification.eq(spec)].sort_values('supporting_influence',ascending=False)
        for k in [1,2,3,5]:
            keys=ranked_cells.head(k)[['omitted_code','omitted_year']]
            omit={(r.omitted_code,r.omitted_year) for r in keys.itertuples()}
            retain=[(r.municipality_code,r.year) not in omit for r in g.itertuples()]
            drop,sub,_=fit(g.loc[retain],metro)
            row=summary(drop,sub,spec,kind='cell_deletion')
            row.update(omitted_count=k,omitted_codes='; '.join(f'{code}/{year}' for code,year in omit),
                       omitted_municipalities='; '.join(ranked_cells.head(k).omitted_municipality),
                       actual_rows_removed=len(g)-len(sub))
            cumulative.append(row)

save(pd.DataFrame(base_rows),'two_parent_influence_models.csv')
loo=pd.DataFrame(loo); cells=pd.DataFrame(cells); groups=pd.concat(groups,ignore_index=True)
components=pd.concat(components,ignore_index=True); cumulative=pd.DataFrame(cumulative)
save(loo,'two_parent_leave_one_municipality_out.csv')
save(cells,'two_parent_leave_one_cell_out.csv')
save(groups,'two_parent_municipality_contributions.csv')
save(components,'two_parent_residualized_observations.csv')
save(cumulative,'two_parent_cumulative_deletions.csv')

# First differences: only actually observed consecutive years form an annual difference.
observed=data.sort_values(['municipality_code','year']).copy()
for v in ['year','x_pp','U33401_days']:
    observed['lag_'+v]=observed.groupby('municipality_code')[v].shift()
observed['year_gap']=observed.year-observed.lag_year
fd=observed[observed.year_gap.eq(1)].copy()
fd['dx_pp']=fd.x_pp-fd.lag_x_pp
fd['dy_days']=fd.U33401_days-fd.lag_U33401_days
fd['start_year']=fd.lag_year.astype(int)
save(fd[['municipality_code','municipality','metro','start_year','year','lag_x_pp','x_pp','dx_pp',
         'lag_U33401_days','U33401_days','dy_days']],'two_parent_first_differences.csv')
check('annual differences are genuinely adjacent',fd.year_gap.eq(1).all())
check('no duplicate municipality/interval',not fd.duplicated(['municipality_code','year']).any())
fd_rows=[]; fdloo=[]; fdcumulative=[]

def fd_fit(g,spec,metro=False,se='cluster',intervals=True):
    g=g.copy(); g['x_pp']=g.dx_pp
    if intervals:
        formula='dy_days ~ x_pp + '+('C(metro)*C(year)' if metro else 'C(year)')
    else:
        formula='dy_days ~ x_pp'+(' + C(metro)' if metro else '')
    model=smf.ols(formula,g)
    assert np.linalg.matrix_rank(model.exog)==model.exog.shape[1]
    if se=='cluster':
        res=model.fit(cov_type='cluster',cov_kwds={'groups':g.municipality_code,'use_correction':True},use_t=True)
    else: res=model.fit(cov_type='HC3',use_t=True)
    verify_covariance(model,res,g,se=='cluster')
    row=summary(res,g,spec,kind='first_difference')
    row['standard_errors']='municipality clustered; t(G-1)' if se=='cluster' else 'HC3; t(n-k)'
    return res,row

for label,g,metro in [('FD_adjacent_unbalanced',fd,False),
    ('FD_adjacent_balanced',fd[fd.municipality_code.isin(balanced_codes)],False),
    ('FD_adjacent_metro_interval_unbalanced',fd,True),
    ('FD_adjacent_metro_interval_balanced',fd[fd.municipality_code.isin(balanced_codes)],True)]:
    res,row=fd_fit(g,label,metro); fd_rows.append(row)
    for code in g.municipality_code.unique():
        drop,r=fd_fit(g[g.municipality_code.ne(code)],label,metro)
        r.update(omitted_code=code,omitted_municipality=g.loc[g.municipality_code.eq(code),'municipality'].iloc[0],
                 full_coefficient=res.params['x_pp'],supporting_influence=res.params['x_pp']-drop.params['x_pp'])
        fdloo.append(r)
for end,g in fd.groupby('year'):
    for metro in [False,True]:
        label=f'FD_{end-1}_{end}'+('_metro_controls' if metro else '')
        res,row=fd_fit(g,label,metro,se='HC3',intervals=False); fd_rows.append(row)
ends=data[data.year.isin([2022,2024])].pivot(index=['municipality_code','municipality','metro'],columns='year',values=['x_pp','U33401_days']).dropna()
endpoint=ends.index.to_frame(index=False)
endpoint['dx_pp']=ends['x_pp'][2024].to_numpy()-ends['x_pp'][2022].to_numpy()
endpoint['dy_days']=ends['U33401_days'][2024].to_numpy()-ends['U33401_days'][2022].to_numpy()
for metro in [False,True]:
    label='FD_endpoint_2022_2024'+('_metro_controls' if metro else '')
    res,row=fd_fit(endpoint,label,metro,se='HC3',intervals=False)
    fd_rows.append(row)
    local=[]
    for code in endpoint.municipality_code.unique():
        drop,r=fd_fit(endpoint[endpoint.municipality_code.ne(code)],label,metro,se='HC3',intervals=False)
        r.update(omitted_code=code,omitted_municipality=endpoint.loc[endpoint.municipality_code.eq(code),'municipality'].iloc[0],
                 full_coefficient=res.params['x_pp'],supporting_influence=res.params['x_pp']-drop.params['x_pp'])
        fdloo.append(r); local.append(r)
    ranked=pd.DataFrame(local).sort_values('supporting_influence',ascending=False)
    for k in [1,2,3,5]:
        omitted=ranked.head(k)
        drop,r=fd_fit(endpoint[~endpoint.municipality_code.isin(omitted.omitted_code)],label,metro,se='HC3',intervals=False)
        r.update(omitted_count=k,omitted_codes=','.join(omitted.omitted_code),
                 omitted_municipalities='; '.join(omitted.omitted_municipality))
        fdcumulative.append(r)
save(endpoint,'two_parent_endpoint_differences.csv')
fd_results=pd.DataFrame(fd_rows); save(fd_results,'two_parent_first_difference_models.csv')
save(pd.DataFrame(fdloo),'two_parent_first_difference_leave_one_out.csv')
save(pd.DataFrame(fdcumulative),'two_parent_first_difference_cumulative_deletions.csv')
focus=sorted(set(groups[groups.specification.eq('TWFE_unbalanced')].nlargest(5,'supporting_influence').municipality_code)|{'1419'})
save(data[data.municipality_code.isin(focus)][['municipality_code','municipality','metro','year','x_pp','U33401_days',
    'B_sweden_born_two_foreign_parents','sweden_born_children_0_17']].sort_values(['municipality_code','year']),
    'two_parent_influential_observed_values.csv')
for metro in [False,True]:
    res,g,_=fit(data[data.year.isin([2022,2024])],metro)
    label='FD_endpoint_2022_2024'+('_metro_controls' if metro else '')
    slope=fd_results.set_index('specification').loc[label,'coefficient']
    check('two-wave FE equals endpoint first difference '+str(metro),np.isclose(res.params['x_pp'],slope))

# Validate original main and balanced slopes and clustered SE against archived estimates.
previous=pd.read_csv(OUT/'regressions.csv')
for name,old in [('TWFE_unbalanced','OLS_municipality_year_FE'),('TWFE_balanced','OLS_municipality_year_FE_balanced')]:
    oldrow=previous[(previous.predictor==X)&(previous.specification==old)].iloc[0]
    row=pd.DataFrame(base_rows).set_index('specification').loc[name]
    check('reproduces original coefficient '+name,np.isclose(row.coefficient,oldrow.coefficient,rtol=1e-9))
    check('reproduces original clustered SE '+name,np.isclose(row.std_error,oldrow.std_error,rtol=1e-9))
for spec,g in components.groupby('specification'):
    beta=pd.DataFrame(base_rows).set_index('specification').loc[spec,'coefficient']
    check('cell contributions sum to slope '+spec,np.isclose(g.slope_contribution.sum(),beta))
    check('partial information shares sum to one '+spec,np.isclose(g.partial_x_information_share.sum(),1))
save(pd.DataFrame(checks),'two_parent_influence_checks.csv')

def table(df):
    def f(x):
        if pd.isna(x):return ''
        if isinstance(x,(float,np.floating)):return f'{x:.4f}'
        return str(x).replace('|','\\|')
    return '| '+' | '.join(df.columns)+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join(
        '| '+' | '.join(f(v) for v in row)+' |' for row in df.itertuples(index=False,name=None))+'\n'

top=groups[groups.specification.eq('TWFE_unbalanced')].nlargest(5,'supporting_influence')
ranges=loo.groupby('specification').agg(slope_min=('coefficient','min'),slope_max=('coefficient','max'),
    p_min=('p_value','min'),p_max=('p_value','max'),n_significant_05=('p_value',lambda x:int(x.lt(.05).sum())),n_omissions=('coefficient','size')).reset_index()
text='''# Which municipalities support the two-parent panel association?

Run `python panel_influence.py`. All calculations use the previously saved official 2022–2024 observations. The exposure is 100 × B/(B+C+D), the percentage of Sweden-born children aged 0–17 with two foreign-born parents. No new downloads or imputation were used. Coefficients are days per one percentage point. Every model is re-estimated after a deletion, including all fixed effects and its covariance correction.

## Findings

The positive slope is not attributable to one municipality or one cell alone: every single-municipality and single-cell deletion in the original model leaves a positive slope. Statistical evidence is materially concentrated, however. Öckerö, Nynäshamn and Upplands-Bro together account for about 71% of the signed cross-product between exposure and outcome after removing municipality and year effects. This percentage is a contribution to the regression numerator, not R², a share of cases, or a causal attribution. It conditions on the full-sample residualization, whereas deletion re-estimates that residualization.

The main slope is +6.697 (p=.0048). Omitting Öckerö gives +5.642 (p=.0068); omitting Nynäshamn gives +6.032 (p=.0175); omitting Upplands-Bro gives +6.037 (p=.0574). The last omission weakens precision substantially because Upplands-Bro supplies considerable exposure variation. Across all 43 omissions the slope ranges from +5.642 to +7.168, and 42 of the 43 tests have p<.05. Hence the sign is stable to one municipality, but the 5% classification is not completely stable.

Deleting the three strongest supporting municipalities together gives +3.210, 95% CI [−2.505, 8.926], p=.263. Removing the five strongest gives +1.096 (p=.690). These groups are selected after inspecting influence: they are stress tests, not a defensible reason to discard valid observations or infer that the original estimate is spurious.

## Municipal influence in the original model

'''+table(top[['municipality_code','municipality','coefficient_omitting_municipality','p_omitting_municipality','covariance_share','partial_x_information_share']])+'''
The first three rows account for approximately 71.1% of the signed residual covariance and 41.7% of the residual exposure sum of squares. Staffanstorp and Burlöv are additional supporting municipalities.

## All leave-one-municipality-out ranges

'''+table(ranges)+'''
The balanced sample has 40 municipalities; its slope remains positive under all omissions but is significant in 33/40. With metro-specific year effects, it is significant in 26/43 unbalanced omissions and 0/40 balanced omissions. These are exploratory unadjusted p-values, not independent tests.

## Influential individual municipality-year observations

Öckerö/2022, Tjörn/2024 and Nynäshamn/2022 are the three single cells whose removal most reduces the original slope. Removing Öckerö/2022 alone gives +5.633 (p=.0069). Removing Öckerö/2022 and Tjörn/2024 together gives +4.812, 95% CI [−0.399, 10.022], p=.0694; adding Nynäshamn/2022 gives +3.988 (p=.164).

Upplands-Bro has outcomes only in 2022 and 2024. Removing either leaves a singleton that contributes no within-municipality information, so the remaining singleton is also excluded from FE estimation. The cell-deletion files report actual rows removed; this case is equivalent to omitting the municipality, not a pure one-row influence contrast. All other deleted cells are observed official values, not identified data errors.

'''+table(cells[cells.specification.eq('TWFE_unbalanced')].nlargest(8,'supporting_influence')[
    ['omitted_code','omitted_municipality','omitted_year','actual_rows_removed','coefficient','p_value']])+'''
## Actual trajectories behind the influence

'''+table(data[data.municipality_code.isin(focus)][['municipality_code','municipality','year','x_pp','U33401_days']].sort_values(['municipality_code','year']))+'''
Upplands-Bro combines a +3.33 pp two-parent-share change with a +25-day duration change between 2022 and 2024, but its missing 2023 outcome cannot be interpolated. Nynäshamn combines approximately +2.26 pp with +22 days. Staffanstorp combines approximately +0.98 pp with +52 days. Öckerö's share is almost flat across the endpoints, while its duration falls from 140 to 112 days. It contributes positively after adjustment because its exposure trajectory is compared with the common year pattern; influence is not determined by the raw endpoint change alone. Tjörn's duration is volatile (69, 113, 67 days), despite a much smaller exposure change.

## First differences

Annual first-difference regressions use only actually observed consecutive pairs, with interval indicators for common year changes. No 2022–2024 gap is treated as a one-year difference. Standard errors are municipality-clustered for pooled annual differences. Separate annual or endpoint cross-sections use HC3 errors and t(n−k) intervals. Adding metro × interval indicators allows different annual shocks in each metro. In the endpoint model, an intercept and metro indicators absorb common and metro-specific two-year changes.

'''+table(fd_results[['specification','n','municipalities','coefficient','std_error','ci95_low','ci95_high','p_value']])+'''
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
'''
(OUT/'two_parent_influence_report.md').write_text(text,encoding='utf-8')

# Compare residualized adjacent and endpoint changes without plotting synthetic observations.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(12,4.8))
colors={'Stor-Stockholm':'#2563a6','Stor-Göteborg':'#d87425','Stor-Malmö':'#378661'}
for ax,g,controls,title,label in [
    (axes[0],fd,'C(metro)*C(year)','Adjacent annual changes: 2022–23 and 2023–24','FD_adjacent_metro_interval_unbalanced'),
    (axes[1],endpoint,'C(metro)','Two-year change: 2022–24','FD_endpoint_2022_2024_metro_controls')]:
    z=g.copy()
    z['rx']=smf.ols('dx_pp ~ '+controls,z).fit().resid
    z['ry']=smf.ols('dy_days ~ '+controls,z).fit().resid
    for metro,h in z.groupby('metro'):
        ax.scatter(h.rx,h.ry,color=colors[metro],s=32,alpha=.8,label=metro)
    slope=fd_results.set_index('specification').loc[label,'coefficient']
    grid=np.array([z.rx.min(),z.rx.max()]); ax.plot(grid,grid*slope,color='#444444',linewidth=1.3)
    for r in z[z.municipality_code.isin(['0139','0192','1230','1407'])].itertuples():
        name=r.municipality+(f' {int(r.year)}' if 'year' in z else '')
        ax.annotate(name,(r.rx,r.ry),xytext=(4,4),textcoords='offset points',fontsize=7)
    ax.set(title=title,xlabel='Adjusted change in two-parent share (pp)',ylabel='Adjusted change in duration (days)')
    ax.axhline(0,color='#aaaaaa',linewidth=.6); ax.axvline(0,color='#aaaaaa',linewidth=.6)
    ax.grid(alpha=.15)
axes[0].legend(frameon=False,fontsize=8)
fig.suptitle('Two-parent share: first-difference associations',fontsize=13)
fig.text(.5,.01,'Actual observed changes; metro-specific period changes removed. Descriptive associations, not causal effects.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.04,1,.95]); fig.savefig(OUT/'two_parent_first_differences.png',dpi=180); plt.close(fig)

print('BASE MODELS\n',pd.DataFrame(base_rows).to_string(index=False))
print('\nMUNICIPAL DELETION RANGES\n',loo.groupby('specification').agg(
    slope_min=('coefficient','min'),slope_max=('coefficient','max'),
    p_min=('p_value','min'),p_max=('p_value','max'),positive=('coefficient',lambda x:int(x.gt(0).sum())),
    p_below_05=('p_value',lambda x:int(x.lt(.05).sum())),total=('coefficient','size')).to_string())
print('\nPRIMARY SUPPORTING MUNICIPALITIES\n',groups[groups.specification.eq('TWFE_unbalanced')].sort_values('supporting_influence',ascending=False).head(10).to_string(index=False))
print('\nPRIMARY SUPPORTING CELLS\n',cells[cells.specification.eq('TWFE_unbalanced')].sort_values('supporting_influence',ascending=False).head(10).to_string(index=False))
print('\nCUMULATIVE DELETIONS\n',cumulative.to_string(index=False))
print('\nFIRST DIFFERENCES\n',fd_results.to_string(index=False))
fdloo=pd.DataFrame(fdloo)
print('\nFD DELETION RANGES\n',fdloo.groupby('specification').agg(slope_min=('coefficient','min'),slope_max=('coefficient','max'),
    p_max=('p_value','max'),p_below_05=('p_value',lambda x:int(x.lt(.05).sum())),total=('coefficient','size')).to_string())
print('\nENDPOINT SUPPORTING MUNICIPALITIES\n',fdloo[fdloo.specification.eq('FD_endpoint_2022_2024_metro_controls')].nlargest(5,'supporting_influence').to_string(index=False))
print('\nENDPOINT CUMULATIVE DELETIONS\n',pd.DataFrame(fdcumulative).to_string(index=False))
print('\nFOCUS RAW VALUES\n',data[data.municipality_code.isin(focus)][['municipality_code','municipality','year','x_pp','U33401_days']].sort_values(['municipality_code','year']).to_string(index=False))
print('\nCHECKS',len(checks),'passed')
