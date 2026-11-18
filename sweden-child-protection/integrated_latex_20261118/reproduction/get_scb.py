from fetch import fetch,P
import json
from concurrent.futures import ThreadPoolExecutor
def run(table):
 m=json.loads((P/'raw'/f'{table}_metadata.json').read_text(encoding='utf-8'))
 vals={k:list(v['category']['index']) for k,v in m['dimension'].items()}
 vals['Region']=[x for x in vals['Region'] if len(x)==4];vals['Tid']=['2015']
 if table=='TAB1121':vals['ContentsCode']=['000006R7','000006PT']
 payload={'selection':[{'variableCode':k,'valueCodes':v} for k,v in vals.items()]}
 fetch(f'https://statistikdatabasen.scb.se/api/v2/tables/{table}/data?lang=sv&outputFormat=json-stat2',f'{table}_2015.json',payload)
 print(table,'downloaded')
with ThreadPoolExecutor(2) as ex:list(ex.map(run,['TAB4823','TAB1121']))
