from pathlib import Path
import urllib.request,json,hashlib,datetime,zipfile
P=Path(__file__).resolve().parent
urls={'socialstyrelsen_2026.xlsx':'https://www.socialstyrelsen.se/contentassets/11a181f7bb3f4fd3b827c842b7df21c9/2026-6-10349.xlsx','github_tree.json':'https://api.github.com/repos/duomo77/2ndbrainforsocialscience/git/trees/main?recursive=1'}
logs=[]
for name,url in urls.items():
 try:
  with urllib.request.urlopen(url,timeout=60) as r:b=r.read();status=r.status
  (P/'raw'/name).write_bytes(b)
  logs.append(dict(file=name,url=url,timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
 except Exception as e:logs.append(dict(file=name,url=url,error=repr(e)))
(P/'results/download_log.json').write_text(json.dumps(logs,indent=2),encoding='utf-8')
print(json.dumps(logs,indent=2))
t=json.loads((P/'raw/github_tree.json').read_text())
print('REMOTE CANDIDATES',[(x['path'],x.get('size')) for x in t['tree'] if any(k in x['path'].lower() for k in ['vind','did','sweden']) and not x['path'].startswith('sweden-child-protection/')][:60])
