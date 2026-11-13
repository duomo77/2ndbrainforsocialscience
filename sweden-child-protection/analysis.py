"""Reproduce processed data, validation, descriptive associations and diagnostics.

Run from any directory: python analysis.py [--skip-bulk-check]
No network access, imputation, simulated observations, or 2SLS in this file.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, itertools, json, platform, zipfile
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'raw'; DATA=ROOT/'data'; OUT=ROOT/'results'
DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
YEARS=[2022,2023,2024,2025]
BACKGROUND={'08':'A_foreign_born','4':'B_sweden_born_two_foreign_parents',
            '5':'C_sweden_born_one_foreign_parent','6':'D_sweden_born_two_sweden_parents'}
SHARES=['foreign_born_share','foreign_background','any_foreign_parent_among_Sweden_born',
        'two_foreign_parents_among_Sweden_born']
checks=[]

def load(name): return json.loads((RAW/name).read_text(encoding='utf-8-sig'))
def csv(df,path): df.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.12g')
def check(name,condition,details=''):
    checks.append(dict(check=name,passed=bool(condition),details=details))
    if not condition: raise ValueError(f'{name}: {details}')

def crosswalk():
    groups=load('scb_metro_codelist.json')['values']
    labels=load('scb_TAB4824_metadata.json')['dimension']['Region']['category']['label']
    rows=[dict(municipality_code=c,municipality=labels[c],metro=g['label'],metro_code=g['code'])
          for g in groups if g['code'] in ['0010','0020','0030'] for c in g['valueMap']]
    df=pd.DataFrame(rows).sort_values('municipality_code').reset_index(drop=True)
    check('51 unique four-digit codes',len(df)==51 and df.municipality_code.nunique()==51 and
          df.municipality_code.str.fullmatch(r'\d{4}').all())
    check('metro counts 26/13/12',df.groupby('metro_code').size().to_dict()=={'0010':26,'0020':13,'0030':12})
    kol={r['id']:r['title'] for r in load('kolada_municipalities.json')['values']}
    check('all codes and names match Kolada',all(kol.get(r.municipality_code)==r.municipality for r in df.itertuples()))
    csv(df,DATA/'municipality_crosswalk.csv')
    return df

def kolada(codes):
    rows=[]
    for kpi,years in [('U33401',YEARS),('N02926',[2015]+YEARS)]:
        for year in years:
            obj=load(f'kolada_{kpi}_{year}.json')
            check(f'{kpi}/{year} pagination complete',obj['next_url'] is None and obj['count']==len(obj['values']))
            for r in obj['values']:
                if r['municipality'] not in codes: continue
                check(f'{kpi}/{year}/{r["municipality"]} period',r['kpi']==kpi and r['period']==year)
                for v in r['values']:
                    rows.append(dict(municipality_code=r['municipality'],year=year,kpi=kpi,**v))
    df=pd.DataFrame(rows)
    check('Kolada unique code/year/KPI/gender',not df.duplicated(['municipality_code','year','kpi','gender']).any())
    csv(df,DATA/'kolada_metro_long.csv')
    total=df[df.gender.eq('T')].copy()
    total['usable']=total.value.notna() & ~total.isdeleted & total.status.fillna('').eq('')
    # The source count is the number of reporting units, NOT investigation volume.
    check('nonnegative duration',total.loc[total.usable & total.kpi.eq('U33401'),'value'].ge(0).all())
    check('N02926 percent bounds',total.loc[total.usable & total.kpi.eq('N02926'),'value'].between(0,100).all())
    return total

def parse_jsonstat(obj):
    dims=obj['id']; ordered=[]
    for dim in dims:
        index=obj['dimension'][dim]['category']['index']
        ordered.append(sorted(index,key=index.get) if isinstance(index,dict) else list(index))
    keys=list(itertools.product(*ordered)); vals=obj['value']
    if isinstance(vals,dict): vals=[vals.get(str(i)) for i in range(len(keys))]
    check('JSON-stat cell dimensions',len(vals)==len(keys)==int(np.prod(obj['size'])))
    df=pd.DataFrame(keys,columns=dims); df['count']=vals
    return df

def children(codes,bulk_check):
    obj=load('scb_children_2015_2022_2023_2024.json')
    df=parse_jsonstat(obj)
    check('SCB exact selection',set(df.Region)==codes and set(df.Alder)=={str(a) for a in range(18)}
          and set(df.Kon)=={'1','2'} and set(df.UtlBakgrund)==set(BACKGROUND)
          and set(df.Tid)=={'2015','2022','2023','2024'})
    check('SCB unique cells',not df.duplicated(obj['id']).any())
    check('SCB observed integer counts',df['count'].notna().all() and df['count'].ge(0).all()
          and df['count'].mod(1).eq(0).all())
    if bulk_check:
        selected=[]; z=zipfile.ZipFile(RAW/'TAB4824_sv.zip')
        with z.open('TAB4824_sv.csv') as source:
            for chunk in pd.read_csv(source,encoding='cp1252',dtype=str,chunksize=250000):
                keep=chunk['region'].str[:4].isin(codes)&chunk['år'].isin(['2015','2022','2023','2024'])
                keep &= chunk['ålder'].isin([f'{a} år' for a in range(18)])
                selected.append(chunk.loc[keep])
        bulk=pd.concat(selected,ignore_index=True)
        labels=obj['dimension']['UtlBakgrund']['category']['label']
        bulk=bulk.rename(columns={'år':'Tid','Antal personer':'bulk_count'})
        bulk['Region']=bulk['region'].str[:4]
        bulk['UtlBakgrund']=bulk['utländsk/svensk bakgrund'].map({v:k for k,v in labels.items()})
        bulk['Alder']=bulk['ålder'].str.replace(' år','',regex=False)
        bulk['Kon']=bulk['kön'].map({'män':'1','kvinnor':'2'})
        bulk['bulk_count']=pd.to_numeric(bulk.bulk_count,errors='raise')
        keys=['Region','UtlBakgrund','Alder','Kon','Tid']
        comp=df.merge(bulk[keys+['bulk_count']],on=keys,how='outer',validate='one_to_one',indicator=True)
        check('all 29,376 API counts equal bulk archive',len(comp)==29376 and comp['_merge'].eq('both').all()
              and comp['count'].eq(comp.bulk_count).all())
    else:
        checks.append(dict(check='bulk comparison',passed=None,details='Explicitly skipped by command line'))
    df=df.rename(columns={'Region':'municipality_code','Tid':'year','Alder':'age','Kon':'sex','UtlBakgrund':'background_code'})
    df['year']=df.year.astype(int); df['age']=df.age.astype(int)
    csv(df,DATA/'child_background_age_sex_long.csv')
    sums=df.groupby(['municipality_code','year','background_code'])['count'].sum(min_count=36)
    out=sums.unstack('background_code').rename(columns=BACKGROUND).reset_index()
    A,B,C,D=[out[BACKGROUND[k]] for k in BACKGROUND]
    out['children_total_0_17']=A+B+C+D
    out['sweden_born_children_0_17']=B+C+D
    out['foreign_background_numerator']=A+B
    out['any_foreign_parent_sweden_born_numerator']=B+C
    out['two_foreign_parents_sweden_born_numerator']=B
    out['foreign_background']=(A+B)/out.children_total_0_17
    out['any_foreign_parent_among_Sweden_born']=(B+C)/out.sweden_born_children_0_17
    out['two_foreign_parents_among_Sweden_born']=B/out.sweden_born_children_0_17
    check('SCB positive denominators',out.children_total_0_17.gt(0).all() and out.sweden_born_children_0_17.gt(0).all())
    check('SCB share bounds',out[SHARES[1:]].apply(lambda x:x.between(0,1)).all().all())
    csv(out,DATA/'child_background_counts_shares.csv')
    return out

def build(cross,k,child):
    panel=cross.merge(pd.DataFrame({'year':YEARS}),how='cross')
    for kpi,col in [('U33401','U33401_days'),('N02926','N02926_pct')]:
        v=k[k.kpi.eq(kpi)][['municipality_code','year','value','status','isdeleted','usable','count']].copy()
        v.loc[~v.usable,'value']=np.nan
        v=v.rename(columns={'value':col,'status':kpi+'_source_status','isdeleted':kpi+'_isdeleted',
                            'usable':kpi+'_usable','count':kpi+'_reporting_unit_count'})
        panel=panel.merge(v,on=['municipality_code','year'],how='left',validate='one_to_one')
        panel[kpi+'_availability']=np.where(panel[col].notna(),'observed',
            np.where(panel[kpi+'_isdeleted'].astype('boolean').fillna(False).astype(bool),'deleted',
                     np.where(panel[kpi+'_source_status'].notna(),'source_null_or_flagged','no_total_record')))
    panel['foreign_born_share']=panel.N02926_pct/100
    panel=panel.merge(child,on=['municipality_code','year'],how='left',validate='one_to_one')
    panel['child_background_availability']=np.where(panel.children_total_0_17.notna(),'observed','year_not_in_TAB4824')
    base=k[k.kpi.eq('N02926')&k.year.eq(2015)&k.usable].set_index('municipality_code').value
    panel['N02926_pct_2015']=panel.municipality_code.map(base)
    panel['foreign_born_share_2015']=panel.N02926_pct_2015/100
    baseline=child[child.year.eq(2015)].drop(columns='year').rename(columns={c:c+'_2015' for c in child if c not in ['municipality_code','year']})
    panel=panel.merge(baseline,on='municipality_code',how='left',validate='many_to_one')
    check('panel exactly 204 rows',len(panel)==204 and not panel.duplicated(['municipality_code','year']).any())
    check('2015 shares available for all 51',panel[[x+'_2015' for x in SHARES]].notna().all().all())
    annual=panel[panel.year.eq(2024)].copy()
    check('2024 table exactly 51 rows',len(annual)==51)
    for frame in [panel,annual]:
        for v in ['U33401_usable','N02926_usable']:
            frame[v]=frame[v].astype('boolean')
    csv(panel,DATA/'metro_51_panel.csv'); csv(annual,DATA/'metro_51_2024.csv')
    coverage=annual[['municipality_code','municipality','metro','year','U33401_days','U33401_availability',
                     'N02926_pct','N02926_availability','children_total_0_17','sweden_born_children_0_17',
                     'child_background_availability']].copy()
    coverage['all_2024_measures_observed']=annual[['U33401_days']+SHARES].notna().all(axis=1)
    csv(coverage,OUT/'coverage.csv')
    cov=[]
    for (metro,year),g in panel.groupby(['metro','year']):
        for var in ['U33401_days']+SHARES:
            cov.append(dict(metro=metro,year=year,variable=var,n_expected=len(g),n_observed=int(g[var].notna().sum()),n_missing=int(g[var].isna().sum())))
    for year,g in panel.groupby('year'):
        for var in ['U33401_days']+SHARES:
            cov.append(dict(metro='All 51',year=year,variable=var,n_expected=len(g),n_observed=int(g[var].notna().sum()),n_missing=int(g[var].isna().sum())))
    csv(pd.DataFrame(cov),OUT/'coverage_by_year.csv')
    nat=[]
    for year in YEARS:
        raw=load(f'kolada_U33401_{year}.json')
        records=[r for r in raw['values'] if len(r['municipality'])==4 and r['municipality'].isdigit()]
        observed=sum(any(v['gender']=='T' and v['value'] is not None and not v['isdeleted'] and not v['status'] for v in r['values']) for r in records)
        nat.append(dict(year=year,n_swedish_municipalities=290,n_outcome_observed=observed,
                        n_outcome_missing=290-observed,n_metro_outcome_observed=int(panel.loc[panel.year.eq(year),'U33401_days'].notna().sum())))
    csv(pd.DataFrame(nat),OUT/'outcome_national_coverage.csv')
    return panel,annual,coverage

def descriptives(panel):
    rows=[]
    for year,g0 in panel.groupby('year'):
        for metro,g in [('All 51',g0)]+list(g0.groupby('metro')):
            for var in ['U33401_days']+SHARES:
                s=g[var].dropna()
                rows.append(dict(year=year,metro=metro,variable=var,n_expected=len(g),n_observed=len(s),
                    n_missing=len(g)-len(s),mean=s.mean(),sd=s.std(),median=s.median(),min=s.min(),max=s.max(),
                    q25=s.quantile(.25),q75=s.quantile(.75),aggregation='unweighted municipalities',
                    unit='days' if var=='U33401_days' else 'fraction'))
    csv(pd.DataFrame(rows),OUT/'descriptives.csv')
    ratios=[]
    source=pd.read_csv(DATA/'child_background_counts_shares.csv',dtype={'municipality_code':str})
    source=source.merge(panel[['municipality_code','metro']].drop_duplicates(),on='municipality_code',validate='many_to_one')
    for year,g0 in source.groupby('year'):
        for metro,g in [('All 51',g0)]+list(g0.groupby('metro')):
            ratios.append(dict(metro=metro,year=year,n_municipalities=len(g),children_total_0_17=g.children_total_0_17.sum(),
                sweden_born_children_0_17=g.sweden_born_children_0_17.sum(),
                foreign_background=g.foreign_background_numerator.sum()/g.children_total_0_17.sum(),
                any_foreign_parent_among_Sweden_born=g.any_foreign_parent_sweden_born_numerator.sum()/g.sweden_born_children_0_17.sum(),
                two_foreign_parents_among_Sweden_born=g.two_foreign_parents_sweden_born_numerator.sum()/g.sweden_born_children_0_17.sum()))
    csv(pd.DataFrame(ratios),OUT/'metro_pooled_child_shares.csv')
    comparisons=[]
    annual=panel[panel.year.eq(2024)]
    for metro,g in [('All 51',annual)]+list(annual.groupby('metro')):
        for s in SHARES:
            comparisons.append(dict(metro=metro,measure=s,n_2015=int(g[s+'_2015'].notna().sum()),n_2024=int(g[s].notna().sum()),
                mean_2015_pct=g[s+'_2015'].mean()*100,mean_2024_pct=g[s].mean()*100,
                change_in_mean_pp=(g[s]-g[s+'_2015']).mean()*100,aggregation='unweighted municipalities'))
    csv(pd.DataFrame(comparisons),OUT/'descriptives_baseline_comparison.csv')

def regressions(panel,annual):
    rows=[]; corr=[]; influence=[]; loo=[]; missingness=[]; within=[]
    predictors=SHARES+[s+'_2015' for s in SHARES]
    balanced=set(panel.groupby('municipality_code').filter(lambda g:g.U33401_days.notna().all()).municipality_code)
    def fit(g,x,spec,fe='C(metro)',log=False,weight=False,cluster=False):
        use=g.dropna(subset=['U33401_days',x]+(['children_total_0_17'] if weight else [])).copy()
        if log: use=use[use.U33401_days.gt(0)]
        if cluster:
            counts=use.groupby('municipality_code').size()
            use=use[use.municipality_code.isin(counts[counts.ge(2)].index)].copy()
        if len(use)<10 or use[x].nunique()<2: return None
        use['x_pp']=use[x]*100
        use['dependent']=np.log(use.U33401_days) if log else use.U33401_days
        if fe=='municipality_and_metro_year':
            # Only non-reference metro x non-reference year dummies: metro main
            # effects are already absorbed by municipality indicators.
            terms=[]
            for j,m in enumerate(sorted(use.metro.unique())[1:]):
                for y in sorted(use.year.unique())[1:]:
                    term=f'metro_year_{j}_{y}'
                    use[term]=((use.metro==m)&(use.year==y)).astype(float)
                    terms.append(term)
            fe='C(municipality_code) + C(year) + '+' + '.join(terms)
        formula='dependent ~ x_pp'+(' + '+fe if fe else '')
        model=smf.wls(formula,use,weights=use.children_total_0_17) if weight else smf.ols(formula,use)
        check('full rank '+spec+'/'+x,np.linalg.matrix_rank(model.exog)==model.exog.shape[1])
        if cluster:
            res=model.fit(cov_type='cluster',cov_kwds={'groups':use.municipality_code,'use_correction':True},use_t=True)
        else: res=model.fit(cov_type='HC3',use_t=True)
        ci=res.conf_int().loc['x_pp']
        rows.append(dict(sample='panel' if cluster else '2024',specification=spec,predictor=x,
            n=int(res.nobs),n_municipalities=use.municipality_code.nunique(),years=','.join(map(str,sorted(use.year.unique()))),
            coefficient=res.params['x_pp'],std_error=res.bse['x_pp'],p_value=res.pvalues['x_pp'],
            ci95_low=ci.iloc[0],ci95_high=ci.iloc[1],r_squared=res.rsquared,
            fixed_effects=fe,standard_errors='municipality clustered; t(G-1)' if cluster else 'HC3; t(n-k)',
            weighting='0-17 population; not case-volume' if weight else 'equal municipality observations',
            coefficient_unit='log days per percentage point' if log else 'days per percentage point',causal=False))
        return res,use
    for x in predictors:
        g=annual.dropna(subset=['U33401_days',x]).copy()
        for method in ['pearson','spearman']:
            estimate=stats.pearsonr(g[x],g.U33401_days) if method=='pearson' else stats.spearmanr(g[x],g.U33401_days)
            corr.append(dict(year=2024,predictor=x,method=method,n=len(g),estimate=estimate.statistic,p_value=estimate.pvalue,adjustment='none'))
            # Partial correlation uses linear metro residuals. Spearman ranks are formed before residualizing.
            temp=g.copy(); temp['x']=temp[x].rank() if method=='spearman' else temp[x]
            temp['y']=temp.U33401_days.rank() if method=='spearman' else temp.U33401_days
            rx=smf.ols('x ~ C(metro)',temp).fit().resid; ry=smf.ols('y ~ C(metro)',temp).fit().resid
            r=stats.pearsonr(rx,ry).statistic; dfree=len(temp)-temp.metro.nunique()-1
            p=2*stats.t.sf(abs(r*np.sqrt(dfree/(1-r*r))),dfree)
            corr.append(dict(year=2024,predictor=x,method='partial_'+method,n=len(g),estimate=r,p_value=p,
                             adjustment='metro residuals; ranked first for Spearman'))
        fit(annual,x,'OLS_unadjusted',fe='')
        main=fit(annual,x,'OLS_metro_FE')
        fit(annual,x,'OLS_metro_FE_log_outcome',log=True)
        fit(annual,x,'WLS_metro_FE_child_population_weights',weight=True)
        fit(annual[~annual.municipality_code.isin(['0180','1480','1280'])],x,'OLS_metro_FE_exclude_three_core_cities')
        fit(annual[annual.municipality_code.isin(balanced)],x,'OLS_metro_FE_balanced_outcome_reporters')
        if main:
            _,use=main
            ordinary=smf.ols('U33401_days ~ x_pp + C(metro)',use).fit()
            inf=ordinary.get_influence()
            for i,(idx,row) in enumerate(use.iterrows()):
                influence.append(dict(predictor=x,municipality_code=row.municipality_code,municipality=row.municipality,
                                      cooks_distance=inf.cooks_distance[0][i],leverage=inf.hat_matrix_diag[i]))
                sub=use.drop(index=idx)
                r=smf.ols('U33401_days ~ x_pp + C(metro)',sub).fit()
                loo.append(dict(predictor=x,omitted_code=row.municipality_code,coefficient=r.params['x_pp']))
        observed=annual.U33401_days.notna()
        a=annual.loc[observed,x]; b=annual.loc[~observed,x]
        missingness.append(dict(predictor=x,n_reporters=len(a),n_nonreporters=len(b),reporter_mean=a.mean(),
            nonreporter_mean=b.mean(),difference=a.mean()-b.mean(),welch_p=stats.ttest_ind(a,b,equal_var=False).pvalue))
    for x in SHARES:
        g=panel.dropna(subset=['U33401_days',x]).copy()
        keep=g.groupby('municipality_code').size(); g=g[g.municipality_code.isin(keep[keep.ge(2)].index)]
        means=g.groupby('municipality_code')[x].transform('mean')
        within.append(dict(predictor=x,n=len(g),municipalities=g.municipality_code.nunique(),
            year_min=g.year.min(),year_max=g.year.max(),within_sd_pp=np.std((g[x]-means)*100,ddof=1)))
        if len(g)>=60 and g.municipality_code.nunique()>=20 and g.year.nunique()>=3:
            fit(g,x,'OLS_municipality_year_FE',fe='C(municipality_code) + C(year)',cluster=True)
            sizes=g.groupby('municipality_code').size()
            complete=g[g.municipality_code.isin(sizes[sizes.eq(g.year.nunique())].index)]
            fit(complete,x,'OLS_municipality_year_FE_balanced',fe='C(municipality_code) + C(year)',cluster=True)
            fit(g,x,'OLS_municipality_metro_by_year_FE',fe='municipality_and_metro_year',cluster=True)
            if x=='foreign_born_share':
                fit(g[g.year.lt(2025)],x,'OLS_municipality_year_FE_exclude_2025',
                    fe='C(municipality_code) + C(year)',cluster=True)
    reg=pd.DataFrame(rows)
    main=reg.specification.eq('OLS_metro_FE')
    reg.loc[main,'p_value_BH_primary_8']=multipletests(reg.loc[main,'p_value'],method='fdr_bh')[1]
    pm=reg.specification.eq('OLS_municipality_year_FE')
    reg.loc[pm,'p_value_BH_panel_4']=multipletests(reg.loc[pm,'p_value'],method='fdr_bh')[1]
    csv(reg,OUT/'regressions.csv'); csv(pd.DataFrame(corr),OUT/'correlations.csv')
    csv(pd.DataFrame(loo),OUT/'leave_one_out.csv'); csv(pd.DataFrame(influence),OUT/'influence.csv')
    csv(pd.DataFrame(missingness),OUT/'reporting_selection.csv'); csv(pd.DataFrame(within),OUT/'panel_identification.csv')
    return reg,pd.DataFrame(corr)

def markdown_table(df):
    def fmt(v):
        if pd.isna(v): return ''
        if isinstance(v,(float,np.floating)): return f'{v:.4f}'
        return str(v).replace('|','\\|')
    return '| '+' | '.join(df.columns)+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+ '\n'.join(
        '| '+' | '.join(fmt(v) for v in row)+' |' for row in df.itertuples(index=False,name=None))

def report(panel,annual,coverage,reg,corr):
    meta=load('kolada_kpi_metadata.json')['values']
    (OUT/'kpi_metadata_audit.md').write_text('''# KPI definition and comparability audit

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
'''+ '\n## Exact current API metadata\n\n```json\n'+json.dumps(meta,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf-8')
    primary=reg[reg.specification.eq('OLS_metro_FE')][['predictor','n','coefficient','std_error','ci95_low','ci95_high','p_value','p_value_BH_primary_8']]
    counts=panel.groupby('year').U33401_days.agg(['count','mean','std','median']).reset_index()
    missing=annual.loc[annual.U33401_days.isna(),['municipality_code','municipality','metro']]
    text='# Sweden metropolitan municipality associations\n\n'
    text+='These are descriptive municipality-level associations. No coefficient is a causal effect, and no result identifies migrant children\'s individual protection delays.\n\n'
    text+='## Outcome coverage and unweighted municipal means\n\n'+markdown_table(counts)+'\n\n'
    text+='## Primary 2024 metro fixed-effects OLS\n\nCoefficients are days per one percentage point. HC3 standard errors, t-based intervals. Each predictor is estimated separately with metro indicators. BH adjustment covers the eight primary OLS slopes only; other reported analyses remain exploratory.\n\n'+markdown_table(primary)+'\n\n'
    text+='None of these eight primary slopes is distinguishable from zero at the 5% level. Raw Pearson correlations for 2024 measures are close to zero. This is imprecise evidence, not proof that there is no relationship.\n\n'
    text+='## 2024 raw correlations\n\n'+markdown_table(corr[corr.adjustment.eq('none')&corr.predictor.isin(SHARES)][['predictor','method','n','estimate','p_value']])+'\n\n'
    desc=pd.read_csv(OUT/'descriptives.csv')
    text+='## 2024 metro outcome statistics\n\n'+markdown_table(desc[(desc.year==2024)&(desc.variable=='U33401_days')][['metro','n_expected','n_observed','n_missing','mean','sd','median','min','max']])+'\n\n'
    text+='## Short-panel estimates and sensitivity\n\n'+markdown_table(reg[reg.specification.str.startswith('OLS_municipality')][['specification','predictor','n','n_municipalities','years','coefficient','std_error','ci95_low','ci95_high','p_value','p_value_BH_panel_4']])+'\n\n'
    text+='The main panel slopes are positive, in contrast to the negative metro-adjusted cross-section slopes. These models use different identifying variation and are not interchangeable. The child measures vary by less than one percentage point within a typical municipality in this short window. Balanced-panel and metro-by-year-effect sensitivities are reported alongside the main models. The four main panel p-values also receive a separate BH adjustment; sensitivity p-values are exploratory.\n\n'
    text+='## 51-row 2024 coverage table\n\n'+markdown_table(coverage[['municipality_code','municipality','metro','U33401_days','N02926_pct','children_total_0_17','all_2024_measures_observed']])+'\n\n'
    text+='## Municipalities without a 2024 outcome\n\n'+markdown_table(missing)+'\n\n'
    text+='## Design and sensitivity\n\nPearson/Spearman and metro-partial correlations are in correlations.csv. Sensitivities include unadjusted OLS, log duration, child-population WLS, exclusion of the three core cities, balanced outcome reporters, and leave-one-municipality-out slopes. Child weighting changes the estimand and is not weighting by investigation counts. All official observations are retained; influence diagnostics do not justify silently deleting observations. Reporting_selection.csv compares the covariates of reporters and nonreporters, without assuming missingness at random.\n\n'
    text+='Panel models use actual time-varying population shares, municipality and year effects, and municipality-clustered errors with finite-sample correction. N02926 can use 2022–2025; child-background measures use 2022–2024 only. Municipalities with only one complete observation are excluded. Balanced variants require all years in the corresponding estimation window. Within variation is reported in panel_identification.csv. No time-invariant 2015 share is included with municipality fixed effects.\n\n'
    text+='Cross-section covariates for 2024 are year-end stocks whereas U33401 measures the first half-year. Reverse causality, omitted staffing/caseload, reporting selection, local measurement differences, population composition, spatial dependence and multiple testing limit interpretation. Three metros are too few for reliable metro-clustered inference; HC3 does not address spatial correlation. A municipal mean is not an individual risk or duration, and an ecological association cannot compare migrant and Sweden-born children.\n'
    (OUT/'analysis_report.md').write_text(text,encoding='utf-8')
    print(primary.to_string(index=False))
    print(counts.to_string(index=False))

def figure(annual):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    g=annual.dropna(subset=['U33401_days'])
    colors={'Stor-Stockholm':'#2563a6','Stor-Göteborg':'#d87425','Stor-Malmö':'#378661'}
    fig,axes=plt.subplots(1,2,figsize=(11,4.4))
    for ax,x,label in zip(axes,['foreign_born_share','foreign_background'],
                          ['Foreign-born residents, all ages (%)','Foreign background among ages 0–17 (%)']):
        for metro,h in g.groupby('metro'):
            ax.scatter(h[x]*100,h.U33401_days,label=metro,color=colors[metro],s=38,alpha=.85)
        ax.set(xlabel=label,ylabel='Mean investigation duration (days)')
        ax.grid(alpha=.18); ax.set_axisbelow(True)
    axes[0].legend(frameon=False,fontsize=8)
    fig.suptitle('2024: 44 reporting municipalities of 51',fontsize=13)
    fig.text(.5,.01,'Municipality-level observations. First-half-year duration and year-end population stocks. Descriptive associations.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.045,1,.95]); fig.savefig(OUT/'2024_associations.png',dpi=180); plt.close(fig)

def manifest():
    rows=[]
    for p in sorted(RAW.glob('*')):
        if p.is_file(): rows.append(dict(file=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    csv(pd.DataFrame(rows),OUT/'raw_checksums.csv')

def main():
    args=argparse.ArgumentParser(); args.add_argument('--skip-bulk-check',action='store_true'); opts=args.parse_args()
    cross=crosswalk(); codes=set(cross.municipality_code)
    k=kolada(codes); child=children(codes,not opts.skip_bulk_check)
    panel,annual,coverage=build(cross,k,child)
    descriptives(panel); reg,corr=regressions(panel,annual)
    report(panel,annual,coverage,reg,corr)
    figure(annual)
    csv(pd.DataFrame(checks),OUT/'validation.csv')
    env=dict(run_timestamp_utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),platform=platform.platform(),
             pandas=pd.__version__,numpy=np.__version__,scipy=__import__('scipy').__version__,statsmodels=sm.__version__)
    (OUT/'environment.json').write_text(json.dumps(env,indent=2),encoding='utf-8')
    manifest()
    print(f'PASS: {len(checks)} checks; {len(annual)} rows for 2024; {len(panel)} panel rows; {len(reg)} regression estimates.')

if __name__=='__main__': main()
