"""Repeat three principal fits, verify raw hashes and report exact new-code repeatability."""
import json,hashlib
import pandas as pd
from analysis import fit
from fetch import P
checks=[]
for row in json.loads((P/'results/raw_checksums.json').read_text(encoding='utf-8')):
 assert hashlib.sha256((P/row['file']).read_bytes()).hexdigest()==row['sha256']
checks.append('All downloaded raw bytes still match recorded SHA-256')
b=pd.read_csv(P/'data/municipality_analysis_wide.csv',dtype={'code':str,'county':str});a=b[b.long_panel]
old=pd.read_csv(P/'results/dml_main.csv')
for r in old.to_dict('records'):
 post,pre=map(int,r['period'].split('-'));v=fit(a,pre,post)
 for k in ['estimate_pp','se_pp','lo_pp','hi_pp','control_ess']:
  assert abs(v[k]-r[k])<1e-10,(k,v[k],r[k])
 checks.append('Repeated independent-code fit agrees to 1e-10: '+r['period'])
report={'passed':True,'checks':checks,'exact_original_implementation_replicated':False,'distinction':'Repeatability of the newly written code is verified. Original code and exact original DML output have not been recovered.'}
(P/'results/execution_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
