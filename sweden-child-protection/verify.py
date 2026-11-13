"""Independent arithmetic/provenance checks, separate from the analysis builder."""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'; RAW=ROOT/'raw'

def main():
    checks=[]
    def test(name,ok,details=''):
        checks.append(dict(check=name,passed=bool(ok),details=details))
        if not ok: raise AssertionError(name+': '+details)
    df=pd.read_csv(ROOT/'data/metro_51_2024.csv',dtype={'municipality_code':str,'metro_code':str})
    panel=pd.read_csv(ROOT/'data/metro_51_panel.csv',dtype={'municipality_code':str,'metro_code':str})
    reg=pd.read_csv(OUT/'regressions.csv')
    test('51 rows with four-digit codes',len(df)==51 and df.municipality_code.str.fullmatch(r'\d{4}').all())
    test('204 unique panel keys',len(panel)==204 and not panel.duplicated(['municipality_code','year']).any())
    test('outcome annual observed counts',panel.groupby('year').U33401_days.count().to_dict()=={2022:42,2023:42,2024:44,2025:41})
    test('no carried-forward 2025 child shares',panel.loc[panel.year.eq(2025),'foreign_background'].isna().all())
    test('all baseline and 2024 exposures present',df[['foreign_born_share','foreign_born_share_2015','foreign_background','foreign_background_2015',
         'any_foreign_parent_among_Sweden_born','two_foreign_parents_among_Sweden_born']].notna().all().all())
    counts=pd.read_csv(ROOT/'data/child_background_counts_shares.csv',dtype={'municipality_code':str})
    A=counts.A_foreign_born; B=counts.B_sweden_born_two_foreign_parents
    C=counts.C_sweden_born_one_foreign_parent; D=counts.D_sweden_born_two_sweden_parents
    for name,calculated in [('children_total_0_17',A+B+C+D),('sweden_born_children_0_17',B+C+D),
        ('foreign_background',(A+B)/(A+B+C+D)),('any_foreign_parent_among_Sweden_born',(B+C)/(B+C+D)),
        ('two_foreign_parents_among_Sweden_born',B/(B+C+D))]:
        test('recalculated '+name,np.allclose(counts[name],calculated,rtol=1e-10,atol=1e-11))
    primary=reg[reg.specification.eq('OLS_metro_FE')]
    for row in primary.itertuples():
        g=df.dropna(subset=['U33401_days',row.predictor]).copy()
        x=g[row.predictor]*100; y=g.U33401_days
        rx=x-x.groupby(g.metro).transform('mean'); ry=y-y.groupby(g.metro).transform('mean')
        slope=np.dot(rx,ry)/np.dot(rx,rx)
        test('FWL cross-section slope '+row.predictor,np.isclose(slope,row.coefficient,rtol=1e-9,atol=1e-9))
        # Direct matrix HC3 sandwich, independently of the formula/model API.
        metro_dummies=pd.get_dummies(g.metro,drop_first=True,dtype=float).to_numpy()
        X=np.column_stack([np.ones(len(g)),x,metro_dummies])
        bread=np.linalg.inv(X.T@X); beta=bread@X.T@y.to_numpy()
        resid=y.to_numpy()-X@beta; h=np.sum((X@bread)*X,axis=1)
        meat=X.T@(((resid/(1-h))**2)[:,None]*X)
        se=np.sqrt((bread@meat@bread)[1,1])
        test('independent HC3 SE '+row.predictor,np.isclose(se,row.std_error,rtol=1e-9,atol=1e-9))
    for row in reg[reg.specification.eq('OLS_municipality_year_FE')].itertuples():
        g=panel.dropna(subset=['U33401_days',row.predictor]).copy()
        n=g.groupby('municipality_code').size(); g=g[g.municipality_code.isin(n[n.ge(2)].index)]
        F=np.column_stack([np.ones(len(g)),pd.get_dummies(g.municipality_code,drop_first=True,dtype=float).to_numpy(),
                          pd.get_dummies(g.year,drop_first=True,dtype=float).to_numpy()])
        x=g[row.predictor].to_numpy()*100; y=g.U33401_days.to_numpy()
        rx=x-F@np.linalg.lstsq(F,x,rcond=None)[0]; ry=y-F@np.linalg.lstsq(F,y,rcond=None)[0]
        slope=np.dot(rx,ry)/np.dot(rx,rx)
        test('independent two-way-FE slope '+row.predictor,np.isclose(slope,row.coefficient,rtol=1e-8,atol=1e-8))
    validation=pd.read_csv(OUT/'validation.csv')
    test('bulk archive equality passed',validation.loc[validation['check'].eq('all 29,376 API counts equal bulk archive'),'passed'].eq(True).all()
         and validation['check'].eq('all 29,376 API counts equal bulk archive').sum()==1)
    test('all analysis checks passed',validation.passed.eq(True).all())
    test('all regression slopes and SE finite',np.isfinite(reg[['coefficient','std_error','p_value','ci95_low','ci95_high']]).all().all())
    test('no 2015 covariates with municipality FE',not ((reg.predictor.str.endswith('_2015')) & reg.specification.str.startswith('OLS_municipality')).any())
    hashes=pd.read_csv(OUT/'raw_checksums.csv')
    for r in hashes.itertuples():
        test('SHA256 '+r.file,hashlib.sha256((ROOT/r.file).read_bytes()).hexdigest()==r.sha256)
    mirror=RAW/'rka_kkik_changes_2025_municipal_mirror.pdf'
    test('recovered official report is a PDF',mirror.read_bytes().startswith(b'%PDF-'))
    for kpi,years in [('U33401',[2022,2023,2024,2025]),('N02926',[2015,2022,2023,2024,2025])]:
        for year in years:
            src=json.loads((RAW/f'kolada_{kpi}_{year}.json').read_text(encoding='utf-8'))
            col='U33401_days' if kpi=='U33401' else ('N02926_pct_2015' if year==2015 else 'N02926_pct')
            observed={r['municipality']:v['value'] for r in src['values'] for v in r['values']
                      if v['gender']=='T' and v['value'] is not None and not v['isdeleted'] and not v['status']}
            target=df if year==2015 else panel[panel.year.eq(year)]
            expected=target.municipality_code.map(observed)
            test(f'CSV values match raw {kpi}/{year}',np.allclose(target[col],expected,equal_nan=True,rtol=1e-10,atol=1e-9))
    pd.DataFrame(checks).to_csv(OUT/'independent_checks.csv',index=False,encoding='utf-8-sig')
    print(f'PASS: {len(checks)} independent checks.')

if __name__=='__main__': main()
