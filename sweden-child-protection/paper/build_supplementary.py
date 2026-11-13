"""Build the separate Korean reader's guide from its Markdown source.
Uses the document-authoring Python runtime (python-docx); no statistical fitting.
"""
from pathlib import Path
import re,json
from docx import Document
from docx.shared import Pt,Mm,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

P=Path(__file__).resolve().parent;O=P/'output';O.mkdir(exist_ok=True)
source=(P/'supplementary_source_ko.md').read_text(encoding='utf-8')
doc=Document();sec=doc.sections[0]
sec.page_width=Mm(210);sec.page_height=Mm(297)
sec.left_margin=sec.right_margin=Mm(22);sec.top_margin=Mm(21);sec.bottom_margin=Mm(20)
sec.header_distance=Mm(10);sec.footer_distance=Mm(10)
doc.core_properties.title='조사기간 101일을 읽는 법';doc.core_properties.author=''
normal=doc.styles['Normal'];normal.font.name='맑은 고딕';normal.font.size=Pt(10.7)
normal._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'맑은 고딕')
normal.paragraph_format.line_spacing=1.38;normal.paragraph_format.space_after=Pt(7)
for name,size in [('Title',20),('Subtitle',11),('Heading 1',14),('Heading 2',12)]:
 style=doc.styles[name];style.font.name='맑은 고딕';style.font.size=Pt(size);style.font.color.rgb=RGBColor(0,0,0)
 style._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'맑은 고딕');style.paragraph_format.keep_with_next=True
 style.paragraph_format.space_before=Pt(12);style.paragraph_format.space_after=Pt(7)
 if name=='Title':style.paragraph_format.space_before=Pt(0)
 style.font.italic=False
for style in doc.styles:
 if style.type==1:
  for border in list(style.element.xpath('.//w:pBdr')):border.getparent().remove(border)
header=sec.header.paragraphs[0];header.text='SUPPLEMENTARY   스웨덴 아동보호 연구 데이터 해설'
for r in header.runs:r.font.size=Pt(8);r.font.color.rgb=RGBColor(0,0,0);r.font.italic=False
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)

def inline(p,text):
 # Accessible native hyperlinks; literal code labels keep the same readable Korean font.
 for token in re.split(r'(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|`[^`]+`)',text):
  if not token:continue
  m=re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)',token)
  if m:
   link=OxmlElement('w:hyperlink');link.set(qn('r:id'),p.part.relate_to(m[2],RT.HYPERLINK,is_external=True))
   r=OxmlElement('w:r');pr=OxmlElement('w:rPr');c=OxmlElement('w:color');c.set(qn('w:val'),'000000');pr.append(c);r.append(pr);t=OxmlElement('w:t');t.text=m[1];r.append(t);link.append(r);p._p.append(link)
  else:
   r=p.add_run(token.strip('`').strip('*'))
   if token.startswith('**'):r.bold=True

tables=[]
def table(lines):
 rows=[[v.strip() for v in line.strip().strip('|').split('|')] for line in lines]
 rows=[r for r in rows if not all(re.fullmatch(r':?-+:?',v) for v in r)]
 n=len(rows[0]);assert all(len(r)==n for r in rows)
 tbl=doc.add_table(rows=0,cols=n);tbl.alignment=WD_TABLE_ALIGNMENT.CENTER;tbl.autofit=False
 widths={2:[61,105],3:[39,62,65],4:[59,36,48,23]}[n]
 # Special data table: compact code column, wider verbal definition.
 if rows[0][0]=='기호':widths=[14,115,37]
 for col,w in zip(tbl.columns,widths):col.width=Mm(w)
 pr=tbl._tbl.tblPr;borders=OxmlElement('w:tblBorders')
 for edge in ['top','bottom','left','right','insideH','insideV']:
  el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
 pr.append(borders)
 for i,values in enumerate(rows):
  row=tbl.add_row();row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
  if i==0:row._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
  for j,(cell,text) in enumerate(zip(row.cells,values)):
   cell.width=Mm(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   pp=cell.paragraphs[0];pp.paragraph_format.space_after=Pt(4);pp.paragraph_format.space_before=Pt(4);pp.paragraph_format.line_spacing=1.24
   pp.paragraph_format.keep_with_next=(len(rows)<=5 or i==0)
   inline(pp,text)
   for r in pp.runs:r.font.size=Pt(9.6);r.bold=i==0
   if i==0:
    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'EDEDED');cell._tc.get_or_add_tcPr().append(shade)
 p=doc.add_paragraph();p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(0)
 tables.append(rows)

lines=source.splitlines();i=0
while i<len(lines):
 line=lines[i].strip()
 if not line:i+=1;continue
 if line.startswith('|'):
  block=[]
  while i<len(lines) and lines[i].strip().startswith('|'):block.append(lines[i]);i+=1
  table(block);continue
 if line.startswith('# '):doc.add_paragraph(line[2:],'Title');doc.add_paragraph('SUPPLEMENTARY   데이터 해설 자료','Subtitle')
 elif line.startswith('## '):doc.add_paragraph(line[3:],'Heading 1')
 elif line.startswith('### '):doc.add_paragraph(line[4:],'Heading 2')
 else:
  p=doc.add_paragraph();inline(p,line)
 i+=1
for p in doc.paragraphs:
 snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'0');p._p.get_or_add_pPr().append(snap)
doc.save(O/'SUPPLEMENTARY_Data_Guide_KO.docx')
(O/'SUPPLEMENTARY_Data_Guide_KO.md').write_text(source,encoding='utf-8')
(P/'supplementary_table_manifest.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf-8')
print('Supplementary DOCX:',len(doc.paragraphs),'paragraphs;',len(doc.tables),'tables')
