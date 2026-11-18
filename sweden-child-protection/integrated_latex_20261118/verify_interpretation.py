from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parent
manifest=json.loads((P/'SHA256SUMS.json').read_text(encoding='utf-8'))
checked=[]
for r in manifest:
 name=r['file']
 if name.startswith(('data/','reproduction/raw/','reproduction/data/','reproduction/results/')) and not name.endswith('interpretation_preservation.json'):
  p=P/name
  assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],name
  checked.append(name)
s=(P/'main.tex').read_text(encoding='utf-8')
assert s.count('\\section{')==4
assert '@@' not in s
assert '새로운 관측값과 신뢰구간을 생성하지 않았다.' not in s
assert len(json.loads((P/'table_transcription.json').read_text(encoding='utf-8')))==20
report=dict(passed=True,empirical_files_unchanged=len(checked),files=checked,new_estimation=False,model_selection=False,scope='Interpretation and narrative editing only; compared data/raw/results bytes with previous package SHA256SUMS',structure='Four sections, body ends in IV; bibliography follows')
(P/'reproduction/results/interpretation_preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Preserved',len(checked),'empirical files; four sections and 20 tables')
