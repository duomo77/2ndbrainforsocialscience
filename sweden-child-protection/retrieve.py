"""Official-source retrieval. Every HTTP response and exception is logged."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, platform, sys, time
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
RAW.mkdir(parents=True, exist_ok=True)

def fetch(url, name, method='GET', payload=None, timeout=90, refresh=False):
    path = RAW / name
    if path.exists() and not refresh:
        previous=[]
        if (RAW/'requests.jsonl').exists():
            previous=[json.loads(line) for line in (RAW/'requests.jsonl').read_text(encoding='utf-8').splitlines()
                      if json.loads(line).get('file')=='raw/'+name]
        if previous and previous[-1].get('status')==200 and not previous[-1].get('error'):
            if hashlib.sha256(path.read_bytes()).hexdigest()==previous[-1]['sha256']:
                return path
    entry = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), method=method,
                 url=url, request_json=payload, file='raw/'+name)
    start = time.monotonic()
    try:
        r = requests.request(method, url, json=payload, timeout=timeout,
                             headers={'User-Agent':'EmpiricalResearch/1.0 (official open-data retrieval)'})
        entry.update(status=r.status_code, final_url=r.url, response_headers=dict(r.headers),
                     bytes=len(r.content), sha256=hashlib.sha256(r.content).hexdigest())
        if r.status_code>=400:
            path=RAW/(name+'.http_error.txt')
            entry['file']='raw/'+path.name
        path.write_bytes(r.content)
        r.raise_for_status()
    except Exception as exc:
        entry.update(error_type=type(exc).__name__, error=repr(exc))
        raise
    finally:
        entry['elapsed_seconds'] = time.monotonic()-start
        with (RAW/'requests.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(entry,ensure_ascii=False)+'\n')
    return path

if __name__ == '__main__':
    from concurrent.futures import ThreadPoolExecutor
    jobs = [
      ('https://api.kolada.se/v3/docs','kolada_docs.html'),
      ('https://api.kolada.se/v3/openapi.json','kolada_openapi.json'),
      ('https://api.kolada.se/v3/kpi/U33401,N02926','kolada_kpi_metadata.json'),
      ('https://api.kolada.se/v3/municipality','kolada_municipalities.json'),
      ('https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/funktionella-regioner-och-kommungrupper/','scb_metro_index.html'),
      ('https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101Q/UtlSvBakgFin/','scb_table.html'),
      ('https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB4824_sv.zip','TAB4824_sv.zip'),
      ('https://www.kolada.se/verktyg/fri-sokning/','kolada_free_search.html'),
      ('https://statistikdatabasen.scb.se/swagger/v2/swagger.json','scb_openapi.json'),
      ('https://statistikdatabasen.scb.se/api/v2/tables/TAB4824/metadata?lang=sv','scb_TAB4824_metadata.json'),
      ('https://statistikdatabasen.scb.se/api/v2/tables/TAB4824?lang=sv','scb_TAB4824_info.json'),
      ('https://statistikdatabasen.scb.se/api/v2/codeLists/agg_RegionStoromr05-_1?lang=sv','scb_metro_codelist.json'),
      ('https://www.scb.se/contentassets/c4b8142033a9440ca53725ca32321a74/storstadsomr.xls','scb_metros.xls'),
      ('https://www.scb.se/contentassets/c4b8142033a9440ca53725ca32321a74/storstadsomr.pdf','scb_metros.pdf'),
      ('https://rka.nu/radetforframjandeavkommunalaanalyser/koladastod/publicerastatistikikolada.81664.html','rka_reporting.html'),
      ('https://rka.nu/radetforframjandeavkommunalaanalyser/koladastod/publicerastatistikikolada/formularinrapporteringforkkik.44880.html','rka_kkik_forms.html'),
      ('https://extra.skr.se/download/18.21af19d319762784ac14a0eb/1750176036743/F%C3%B6r%C3%A4ndringar%20i%20insamlingen%20av%20data%20till%20KKiK%202025.pdf','rka_kkik_changes_2025.pdf'),
      ('https://politik.enkoping.se/welcome-sv/namnder-styrelser/kommunfullmaktige/kommunfullmaktige-2025-11-04/agenda/forandringar-i-insamlingen-av-data-till-kkik-2025pdf?downloadMode=download','rka_kkik_changes_2025_municipal_mirror.pdf'),
      ('https://www.kolada.se/','kolada_home.html'),
      ('https://www.ifau.se/globalassets/pdf/se/2005/wp05-08.pdf','ifau_refugee_dispersal.pdf'),
      ('https://www.nber.org/papers/w24997','bhj_shift_share.html'),
      ('https://www.nber.org/papers/w24944','akm_shift_share.html'),
      ('https://www.nber.org/papers/w24285','jrs_immigration_instruments.html'),
      ('https://www.migrationsverket.se/Om-Migrationsverket/Statistik/Anvisning-till-kommuner-och-bosattning.html','migration_agency_settlement.html'),
    ]
    for kpi,years in [('U33401',[2024,2022,2023,2025]),('N02926',[2015,2024,2022,2023,2025])]:
        for year in years:
            jobs.append((f'https://api.kolada.se/v3/data/kpi/{kpi}/year/{year}',f'kolada_{kpi}_{year}.json'))
    def run(job):
        try:
            p=fetch(*job)
            return p.name,p.stat().st_size
        except Exception as e:
            return job[1],repr(e)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(run,jobs): print(result,flush=True)
