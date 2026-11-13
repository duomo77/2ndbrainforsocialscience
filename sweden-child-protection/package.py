"""Build source provenance and one complete ZIP, then verify archive contents."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile
import pandas as pd

ROOT=Path(__file__).resolve().parent; RAW=ROOT/'raw'; OUT=ROOT/'results'

def main():
    attempts=[json.loads(s) for s in (RAW/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
    relocation_file=RAW/'error_file_relocations.json'
    relocations=json.loads(relocation_file.read_text(encoding='utf-8')) if relocation_file.exists() else []
    for entry in attempts:
        old=ROOT/entry['file']
        if entry.get('status',0)>=400 and old.exists() and old.suffix=='.pdf':
            new=Path(str(old)+'.http_error.txt')
            assert old.resolve().parent==RAW.resolve() and new.resolve().parent==RAW.resolve()
            if new.exists():
                assert new.read_bytes()==old.read_bytes()
            else: old.rename(new)
            relocations.append(dict(original_file=entry['file'],stored_file=new.relative_to(ROOT).as_posix(),
                                    sha256=entry['sha256'],relocated_at_utc=datetime.now(timezone.utc).isoformat()))
    relocation_file.write_text(json.dumps(relocations,indent=2),encoding='utf-8')
    moved={r['original_file']:r['stored_file'] for r in relocations}
    sources=[]
    for e in attempts:
        file=moved.get(e['file'],e['file']); p=ROOT/file
        sources.append(dict(timestamp_utc=e['timestamp_utc'],method=e['method'],source_url=e['url'],
             final_url=e.get('final_url'),status=e.get('status'),file=file,bytes=e.get('bytes'),sha256=e.get('sha256'),
             content_type=e.get('response_headers',{}).get('Content-Type'),error=e.get('error'),
             stored_checksum_matches=p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==e.get('sha256')))
    pd.DataFrame(sources).to_csv(OUT/'source_manifest.csv',index=False,encoding='utf-8-sig')
    hashes=[dict(file=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(RAW.iterdir()) if p.is_file()]
    pd.DataFrame(hashes).to_csv(OUT/'raw_checksums.csv',index=False,encoding='utf-8-sig')
    # Include only the requested research package, never sibling workspace files or environments.
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not any(s in p.relative_to(ROOT).parts for s in ['__pycache__','.venv','node_modules','.git','tmp'])]
    archive=ROOT.parent/'sweden_metro_51_bundle.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(paths): z.write(p,arcname='sweden_metro_51/'+p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        required=['raw/TAB4824_sv.zip','data/metro_51_2024.csv','data/metro_51_panel.csv',
                  'results/coverage.csv','results/descriptives.csv','results/regressions.csv','results/iv_audit.md','analysis.py','README.md']
        for name in required: assert 'sweden_metro_51/'+name in z.namelist(),name
        for p in paths:
            member='sweden_metro_51/'+p.relative_to(ROOT).as_posix()
            assert hashlib.sha256(z.read(member)).hexdigest()==hashlib.sha256(p.read_bytes()).hexdigest()
    print(f'PASS: {len(paths)} files archived and SHA256-verified. {archive.name}: {archive.stat().st_size:,} bytes')
    print('ZIP SHA256:',hashlib.sha256(archive.read_bytes()).hexdigest())

if __name__=='__main__': main()
