"""Render either final document's actual Word-exported PDF for visual review."""
from pathlib import Path
import sys,json,hashlib
from pypdf import PdfReader
from pdf2image import convert_from_path
from PIL import Image,ImageDraw
from docx import Document

P=Path(__file__).resolve().parent
name=sys.argv[1];assert name in ['Sweden_ChildProtection_Policy_Draft_KO','SUPPLEMENTARY_Data_Guide_KO']
pdf=P/'output'/f'{name}.pdf';out=P/'tmp'/name;out.mkdir(parents=True,exist_ok=True)
reader=PdfReader(pdf);images=convert_from_path(pdf,dpi=130,thread_count=2)
diagnostics=[]
for i,(page,im) in enumerate(zip(reader.pages,images),start=1):
 text=page.extract_text() or '';im.save(out/f'page-{i:02}.png')
 diagnostics.append(dict(page=i,characters=len(text),first_lines=text.splitlines()[:3],last_lines=text.splitlines()[-3:]))
for start in range(0,len(images),6):
 sheet=Image.new('RGB',(960,960),'white')
 for pos,im in enumerate(images[start:start+6]):
  tile=Image.new('RGB',(320,480),'#dddddd');small=im.copy();small.thumbnail((300,440));tile.paste(small,((320-small.width)//2,10));ImageDraw.Draw(tile).text((8,460),f'Page {start+pos+1}',fill='black');sheet.paste(tile,((pos%3)*320,(pos//3)*480))
 sheet.save(out/f'contact-{start//6+1:02}.png')
(out/'diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
full='\n'.join(p.extract_text() or '' for p in reader.pages)
assert all(d['characters']>250 for d in diagnostics),'Unexpectedly sparse page'
assert '\ufffd' not in full and '\u25a1' not in full
doc=Document(P/'output'/f'{name}.docx')
if name=='SUPPLEMENTARY_Data_Guide_KO':
 assert len(doc.tables)==5
 assert all(v in full for v in ['6,298','5,662','1,185','28.91','34.23','20.93','204','169','6.70','1.76'])
 assert '101' in doc.paragraphs[0].text
 assert len(doc.element.xpath('//w:pBdr'))==0
 assert not doc.core_properties.author
else:assert len(doc.tables)==13 and len(doc.element.xpath('//m:oMath'))==6
report=dict(document=name,pages=len(reader.pages),tables=len(doc.tables),structural_checks_passed=True,
            pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),render_method='Word COM PDF export followed by Poppler 130 dpi images')
(P/(name+'_validation.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report));print([(v['page'],v['characters']) for v in diagnostics])
