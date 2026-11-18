from pathlib import Path
import json,itertools,collections,hashlib
import pandas as pd,numpy as np,openpyxl
from fetch import P
def stat(name):
 m=json.loads((P/'raw'/name).read_text(encoding='utf-8-sig'));keys=m['id']
 cats=[sorted(m['dimension'][k]['category']['index'],key=m['dimension'][k]['category']['index'].get) for k in keys]
 v=m['value'];v=[v.get(str(i)) for i in range(np.prod(m['size']))] if isinstance(v,dict) else v
 return pd.DataFrame(itertools.product(*cats),columns=keys).assign(value=v),m
d,m=stat('TAB4823_2015.json');d['value']=pd.to_numeric(d.value,errors='raise')
d['age']=pd.to_numeric(d.Alder.str.replace('+','',regex=False),errors='raise')
g=d.groupby('Region').value.sum();b=pd.DataFrame({'population_2015':g})
b['foreign_born_n_2015']=d[d.Fodelseregion=='11'].groupby('Region').value.sum()
b['foreign_born_pct_2015']=100*b.foreign_born_n_2015/b.population_2015
b['female_pct_2015']=100*d[d.Kon=='2'].groupby('Region').value.sum()/g
b['elderly_pct_2015']=100*d[d.age>=65].groupby('Region').value.sum()/g
b['log_population_2015']=np.log(g)
cut=b.foreign_born_pct_2015.quantile(.75);b['high_foreign_2015']=(b.foreign_born_pct_2015>=cut).astype(int)
b['county']=b.index.str[:2]
inc,im=stat('TAB1121_2015.json')
types=[]
for typ in inc.InkomstTyp.unique():
 t=inc[inc.InkomstTyp==typ].pivot(index='Region',columns='ContentsCode',values='value');t.columns=['poverty_'+typ if c=='000006PT' else 'median_'+typ for c in t.columns]
 b=b.join(t)
 types.append(dict(type=typ,means_by_high=b.groupby('high_foreign_2015')['median_'+typ].mean().to_dict()))
# Disposable income per consumption unit including capital gains; low economic
# standard uses this same income concept. Units are 2024 fixed-price thousand SEK.
b['median_income_2015']=b['median_DispInkInkl'];b['poverty_pct_2015']=b['poverty_DispInkInkl']
w=openpyxl.load_workbook(P/'raw/socialstyrelsen_2026.xlsx',read_only=True,data_only=True)
rows=[r for r in w['DATA'].iter_rows(values_only=True) if r[3]=='VIND28']
allrows=pd.DataFrame(rows,columns=['unique_key','code','name','indicator','label','year','raw_value'])
allrows.to_csv(P/'data/vind28_all_official_rows.csv',index=False,encoding='utf-8-sig')
mun=allrows[allrows.code.isin(b.index)].copy()
# The official workbook repeats Malmö and contains its aggregate percentage
# beside binary records. Prefer an unambiguous Ja/Nej, retaining duplicates log.
dups=mun[mun.duplicated(['code','year'],keep=False)]
dups.to_csv(P/'results/official_duplicate_rows.csv',index=False,encoding='utf-8-sig')
clean=[]
for key,grp in mun.groupby(['code','year']):
 binary=grp[grp.raw_value.isin(['Ja','Nej'])]
 if len(binary):
  assert binary.raw_value.nunique()==1,('conflicting binary',key)
  clean.append(binary.iloc[0])
 else:
  assert grp.raw_value.astype(str).nunique()==1,('conflicting missing/aggregate',key)
  clean.append(grp.iloc[0])
mun=pd.DataFrame(clean)
mun['y']=mun.raw_value.map({'Ja':1.,'Nej':0.})
wide=mun.pivot(index='code',columns='year',values='y').reindex(b.index)
wide.columns=['y'+str(int(x)) for x in wide.columns]
b=b.join(wide);years=[2018,2019,2020,2021,2022,2023,2025,2026]
b['long_panel']=b[['y'+str(x) for x in years]].notna().all(axis=1)
b['linked_2025_2026']=b[['y2025','y2026']].notna().all(axis=1)
assert len(b)==290 and abs(cut-15.662790386)<1e-8
assert b.long_panel.sum()==191 and b.linked_2025_2026.sum()==263
assert b.loc[['0180','1480'],['y'+str(x) for x in years]].isna().all().all()
assert abs(b[b.long_panel].median_income_2015.mean()-308.20)<.01
assert abs(b[~b.long_panel].median_income_2015.mean()-299.40)<.01
b.index.name='code';b.to_csv(P/'data/municipality_analysis_wide.csv',encoding='utf-8-sig')
sample=b[b.long_panel];summary={'threshold':cut,'expected_threshold':15.662790386,'national_n':len(b),'national_high':int(b.high_foreign_2015.sum()),'long_n':len(sample),'long_high':int(sample.high_foreign_2015.sum()),'linked_n':int(b.linked_2025_2026.sum()),'income_concepts':types,'year_group_counts':[]}
for yr in [2023,2025,2026]:
 for hi,grp in sample.groupby('high_foreign_2015'):summary['year_group_counts'].append(dict(year=yr,high=int(hi),n=len(grp),yes=int(grp['y'+str(yr)].sum())))
assert [x['yes'] for x in summary['year_group_counts']]==[39,17,56,31,69,27]
summary['income_included_excluded_means']=[b[b.long_panel].median_income_2015.mean(),b[~b.long_panel].median_income_2015.mean()]
summary['assertions_passed']=['290 municipalities','Exact national threshold to 1e-8','191/263 sample sizes','Stockholm/Gothenburg aggregates not binary','Six group-year affirmative counts','Included/excluded income means agree to 0.01']
(P/'results/data_validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
