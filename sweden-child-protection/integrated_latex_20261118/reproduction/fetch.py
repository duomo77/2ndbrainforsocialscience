from pathlib import Path
from datetime import datetime,timezone
import requests,json,hashlib
P=Path(__file__).resolve().parent
def fetch(url,name,payload=None):
 p=P/'raw'/name
 if p.exists():return p
 record=dict(url=url,file=name,utc=datetime.now(timezone.utc).isoformat(),payload=payload)
 try:
  r=requests.request('POST' if payload else 'GET',url,json=payload,timeout=60)
  record.update(status=r.status_code,sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content));p.write_bytes(r.content);r.raise_for_status()
 except Exception as e:record['error']=repr(e);raise
 finally:
  with (P/'results/requests.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
 return p
if __name__=='__main__':
 from concurrent.futures import ThreadPoolExecutor
 def get(table):
  p=fetch(f'https://statistikdatabasen.scb.se/api/v2/tables/{table}/metadata?lang=sv',f'{table}_metadata.json')
  m=json.loads(p.read_text(encoding='utf-8-sig'))
  print(table,m.keys())
  for k,v in m.get('dimension',{}).items():
   c=v.get('category',{});print(k,v.get('label'),list(c.get('label',{}).items())[:18])
 with ThreadPoolExecutor(2) as ex:list(ex.map(get,['TAB4823','TAB1121']))
