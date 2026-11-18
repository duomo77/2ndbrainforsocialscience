from pathlib import Path
import json
from pypdf import PdfReader
from pdf2image import convert_from_path
from PIL import Image,ImageOps,ImageDraw
P=Path(__file__).resolve().parent
pop=Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1117-835-0_26.1117.835.0_x64__3k8sg7r9htsxt/dependencies/native/poppler/Library/bin')
if not pop.exists():
    pop=next(Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1117-835-0_26.1117.835.0_x64__3k8sg7r9htsxt/dependencies/native/poppler').rglob('pdftoppm.exe')).parent
out=P/'qa';out.mkdir(exist_ok=True)
pages=convert_from_path(str(P/'main.pdf'),dpi=90,poppler_path=str(pop))
for i,p in enumerate(pages,1):p.save(out/f'page_{i:02}.png')
for start in range(0,len(pages),6):
    sheet=Image.new('RGB',(1200,1260),'#aaa')
    for j,p in enumerate(pages[start:start+6]):
        p.thumbnail((390,590));x=(j%3)*400;y=(j//3)*630
        sheet.paste(p,(x,y+25));ImageDraw.Draw(sheet).text((x+10,y+5),str(start+j+1),fill='black')
    sheet.save(out/f'contact_{start//6+1}.jpg')
r=PdfReader(P/'main.pdf');txt='\n'.join(p.extract_text() or '' for p in r.pages)
(out/'extracted.txt').write_text(txt,encoding='utf-8')
report={'pages':len(r.pages),'tables':len(json.loads((P/'table_transcription.json').read_text(encoding='utf-8'))),'replacement_characters':txt.count('\ufffd'),'placeholders':('@@' in txt),'visual_review':'Contact sheets and full-size selected pages to be inspected'}
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(report)
