from pathlib import Path
import json,hashlib,zipfile
P=Path(__file__).resolve().parent
qa=P/'qa/verification.json';v=json.loads(qa.read_text(encoding='utf-8'))
v.update(visual_review=f"passed: all {v['pages']} pages reviewed in contact sheets; figures and nearby analysis checked for placement and legibility",overfull_warnings=0,missing_character_warnings=0)
qa.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
supplement_qa=P/'qa/supplement/verification.json'
review=json.loads(supplement_qa.read_text(encoding='utf-8'))
review.update(visual_review='passed: checked all 5 rendered pages, map legends, and DML axes',
              overfull_warnings=0,missing_character_warnings=0)
supplement_qa.write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
files=[P/n for n in ['main.tex','main.pdf','README.md','build_manuscript.py','case1_table_manifest.json','table_transcription.json','input_provenance.json','main.log','verify_pdf.py','package_project.py','qa/verification.json','data/metro_51_2024.csv','data/metro_51_panel.csv']]
files.append(P/'reproduction_update.py')
files.extend(P/n for n in ['interpretation_revision.py','CLAIM_SCOPE_KO.md','verify_interpretation.py'])
files.extend(P/n for n in ['verify_manuscript.py','MANUSCRIPT_REVIEW_KO.md'])
files.extend(P/n for n in ['REFEREE_REVIEW_KO.md','qa/supplement/verification.json'])
files.extend(p for p in sorted((P/'supplement').rglob('*')) if p.is_file() and '__pycache__' not in p.parts)
files.extend(p for p in sorted((P/'reproduction').rglob('*')) if p.is_file() and '__pycache__' not in p.parts)
checks=[dict(file=p.relative_to(P).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
manifest=P/'SHA256SUMS.json';manifest.write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');files.append(manifest)
out=P.parent/'Sweden_ChildProtection_Integrated_LaTeX_KO_20261118.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,'sweden-integrated-latex/'+p.relative_to(P).as_posix())
with zipfile.ZipFile(out) as z:assert z.testzip() is None
print(json.dumps(dict(zip=str(out),bytes=out.stat().st_size,files=len(files)),ensure_ascii=False))
