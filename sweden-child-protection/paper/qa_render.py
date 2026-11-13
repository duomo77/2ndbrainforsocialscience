"""Rasterize the actual Word-exported PDF and record page/content diagnostics."""
from pathlib import Path
import json
from pypdf import PdfReader
from pdf2image import convert_from_path
from PIL import Image,ImageOps,ImageDraw

PAPER=Path(__file__).resolve().parent
pdf=PAPER/'output/Sweden_ChildProtection_Policy_Draft_KO.pdf'
out=PAPER/'tmp/qa';out.mkdir(parents=True,exist_ok=True)
r=PdfReader(pdf)
pages=[]
for i,page in enumerate(r.pages):
    t=page.extract_text() or ''
    pages.append({'page':i+1,'width_pt':float(page.mediabox.width),'height_pt':float(page.mediabox.height),
                  'characters':len(t),'first_lines':t.splitlines()[:4],'last_lines':t.splitlines()[-3:]})
(PAPER/'tmp/pdf_text.txt').write_text('\n'.join('=== PAGE '+str(i+1)+' ===\n'+(p.extract_text() or '') for i,p in enumerate(r.pages)),encoding='utf-8')
images=convert_from_path(pdf,dpi=130,thread_count=2)
for i,im in enumerate(images):im.save(out/f'page-{i+1:02d}.png')
for start in range(0,len(images),6):
    tiles=[]
    for i,im in enumerate(images[start:start+6],start=start+1):
        small=im.copy();small.thumbnail((300,450))
        tile=Image.new('RGB',(320,480),'#dddddd');tile.paste(small,((320-small.width)//2,20));ImageDraw.Draw(tile).text((8,460),f'Page {i}',fill='black');tiles.append(tile)
    sheet=Image.new('RGB',(960,960),'white')
    for i,im in enumerate(tiles):sheet.paste(im,((i%3)*320,(i//3)*480))
    sheet.save(out/f'contact-{start//6+1:02d}.png')
(PAPER/'tmp/page_diagnostics.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(pages,ensure_ascii=False,indent=2))
print('Rendered pages:',len(images))
