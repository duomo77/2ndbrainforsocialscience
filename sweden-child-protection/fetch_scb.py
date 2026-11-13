"""Query SCB using the downloaded live v2 OpenAPI and table metadata."""
import json
from retrieve import fetch, RAW

def load(name):
    return json.loads((RAW/name).read_text(encoding='utf-8-sig'))

def main():
    schema=load('scb_openapi.json')
    assert '/tables/{id}/data' in schema['paths']
    meta=load('scb_TAB4824_metadata.json')
    metro=load('scb_metro_codelist.json')
    codes=sorted(c for group in metro['values'] if group['code'] in ['0010','0020','0030'] for c in group['valueMap'])
    assert len(codes)==len(set(codes))==51
    selections={'Region':codes,'UtlBakgrund':['08','4','5','6'],
                'Alder':[str(a) for a in range(18)],'Kon':['1','2'],
                'ContentsCode':['000001NT'],'Tid':['2015','2022','2023','2024']}
    for dim,vals in selections.items():
        assert set(vals)<=set(meta['dimension'][dim]['category']['index'])
    payload={'selection':[{'variableCode':dim,'valueCodes':vals} for dim,vals in selections.items()]}
    (RAW/'scb_child_query.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(fetch('https://statistikdatabasen.scb.se/api/v2/tables/TAB4824/data?lang=sv&outputFormat=json-stat2',
                'scb_children_2015_2022_2023_2024.json','POST',payload),flush=True)

if __name__=='__main__': main()
