"""Check the delivered manuscript against its document structure and saved estimates."""
from pathlib import Path
import csv,json,zipfile,hashlib,re
from pypdf import PdfReader
from docx import Document

P=Path(__file__).resolve().parent;R=P.parent/'results';O=P/'output'
checks=[]
def check(name,ok):
    checks.append({'check':name,'passed':bool(ok)})
    assert ok,name
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
doc=Document(O/'Sweden_ChildProtection_Policy_Draft_KO.docx')
pdf=PdfReader(O/'Sweden_ChildProtection_Policy_Draft_KO.pdf')
full='\n'.join(p.extract_text() or '' for p in pdf.pages)
check('thirteen academic tables',len(doc.tables)==13)
check('six editable native Word equations',len(doc.element.xpath('//m:oMath'))==6)
check('three native fraction expressions',len(doc.element.xpath('//m:f'))==3)
check('no theme border below title',len(doc.element.xpath('//w:pBdr'))==0 and len(doc.styles.element.xpath('//w:pBdr'))==0)
check('all 51 municipal rows retained',len(doc.tables[10].rows)==52)
codes=[r.cells[0].text for r in doc.tables[10].rows[1:]]
check('four-digit codes and uniqueness',len(set(codes))==51 and all(re.fullmatch(r'\d{4}',v) for v in codes))
check('no blank or nearly blank pages',all(len(p.extract_text() or '')>300 for p in pdf.pages))
check('reference page size preserved',all(abs(float(p.mediabox.width)-448)<.2 and abs(float(p.mediabox.height)-655)<.2 for p in pdf.pages))
check('Korean text extracted',all(v in full for v in ['국문초록','정책적 함의','일차차분','참고문헌']))
check('no replacement or box glyphs','\ufffd' not in full and '\u25a1' not in full)
check('no unresolved placeholders','{{' not in full and '{{' not in (O/'Sweden_ChildProtection_Policy_Draft_KO.md').read_text(encoding='utf-8'))
regs=read(R/'regressions.csv')
row=next(v for v in regs if v['predictor']=='two_foreign_parents_among_Sweden_born' and v['specification']=='OLS_municipality_year_FE')
check('primary panel coefficient matches 6.70',round(float(row['coefficient']),2)==6.70)
check('primary panel sample matches 126/43',row['n']=='126' and row['n_municipalities']=='43')
fd=read(R/'two_parent_first_difference_models.csv')
row=next(v for v in fd if v['specification']=='FD_endpoint_2022_2024_metro_controls')
check('endpoint coefficient matches 7.43',round(float(row['coefficient']),2)==7.43)
check('contemporaneous headline statistics included',all(v in full for v in ['100.70','6.70','3.21','7.43']))
check('individual delay not presented as measured','개인별 보호 도달과 인과효과' in full and '미추정' in full)
check('author identity not invented',not doc.core_properties.author)
check('no user computer path in PDF','C:\\Users' not in full and 'kim58' not in full)
check('new timing results and appendix included',all(v in full for v in ['9.78','27.92','부록 C','군집 추론']))
check('one comparison figure embedded',len(doc.inline_shapes)==1)
records=[]
for p in sorted(O.iterdir()):
    if p.is_file():records.append({'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
report={'page_count':len(pdf.pages),'tables':13,'native_equations':6,'checks':checks,'outputs':records,
        'render_method':'Microsoft Word 16 COM PDF export of the actual DOCX; Poppler 130 dpi page images',
        'reference_use':'User-provided format and conceptual framing; prior VIND28/district estimates not re-estimated or pooled'}
(P/'paper_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS:',len(checks),'checks;',len(pdf.pages),'PDF pages')
