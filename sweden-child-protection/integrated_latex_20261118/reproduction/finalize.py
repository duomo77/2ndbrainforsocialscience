from pathlib import Path
import json,hashlib,shutil
import pandas as pd
from fetch import P
v=json.loads((P/'results/data_validation.json').read_text(encoding='utf-8'))
main=pd.read_csv(P/'results/dml_main.csv');sens=pd.read_csv(P/'results/dml_sensitivity.csv');allruns=pd.concat([main,sens],ignore_index=True)
rows=[]
for period,g in allruns.groupby('period',sort=False):
 rows.append(dict(period=period,specifications=len(g),minimum_pp=g.estimate_pp.min(),maximum_pp=g.estimate_pp.max(),positive=int((g.estimate_pp>0).sum()),negative=int((g.estimate_pp<0).sum()),p_below_05=int((g.p_value<.05).sum())))
pd.DataFrame(rows).to_csv(P/'results/sensitivity_summary.csv',index=False)
search={'original_code_found':False,'searched_scopes':['Current workspace and Downloads/Documents/OneDrive code and file-name searches','Additional local econometrics/PycharmProjects/source folders','Connected GitHub repository search for VIND28 including research and archive repositories','Public repository recursive tree','Two downloaded VIND28 LaTeX ZIP listings','Selected relevant connected chat summaries; sandbox links are not locally available files'], 'original_archives':['Sweden_VIND28_Overleaf_Ready.zip','Sweden_VIND28_Scandinavian_Studies_LaTeX.zip'],'archive_contents':'LaTeX/style/readme/three figures only; no estimation code or raw municipal panel','conclusion':'Original exact DML implementation not recovered. Official outcomes and SCB covariates rebuilt and independently estimated. No search result establishes that the original code does not exist elsewhere.'}
(P/'results/code_search_audit.json').write_text(json.dumps(search,ensure_ascii=False,indent=2),encoding='utf-8')
manifest=[]
for p in sorted((P/'raw').iterdir()):
 if p.is_file():manifest.append(dict(file='raw/'+p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(P/'results/raw_checksums.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(rows,indent=2))
