import hashlib
import json
import shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
target=root.parent/'Synthetic_Data'
rows=json.loads((root/'.runtime/fixture-qa/wave-build.json').read_text(encoding='utf-8'))
for wave in [1,2]:
    current=[r for r in rows if r['wave_number']==wave]
    for row in current:
        data=(target/f'Wave_{wave}'/row['file_name']).read_bytes()
        row['sha256']=hashlib.sha256(data).hexdigest();row['bytes']=len(data)
    manifest=target/f'Wave_{wave}'/'manifest.json'
    manifest.write_text(json.dumps({'corpus':'KESTREL-SYNTHETIC-2026-11','documents':current},ensure_ascii=False,indent=2),encoding='utf-8')
    packaged=root/'data/synthetic_waves'/f'Wave_{wave}';packaged.mkdir(parents=True,exist_ok=True)
    for item in current:
        source=target/f'Wave_{wave}'/item['file_name'];destination=packaged/item['file_name']
        if not destination.exists():shutil.copy2(source,destination)
    shutil.copy2(manifest,packaged/'manifest.json')
(target/'README.txt').write_text('PROJECT KESTREL SYNTHETIC WAVES\n\nWave_1: five source files; first-wave application fixture.\nWave_2: six local files for manual ingestion, including C001/P001 version 2.\n\nStart at https://firm.localhost:8443/portal?view=Resources.\nUse lawyer01@freshfields.example for ordinary/privileged intake, cleanteam01@freshfields.example for pricing, sme01 for ordinary analysis and sme03 for named pricing analysis.\nThe existing shared demo password is in your credentials CSV and private .env.\n\nSelect the matching source version when adding C001/P001 from Wave_2; preserve history. Read manifest.json for language, governing law and declared handling. Confirm intake classification, then authorize a published playbook analysis. Review each exact citation before drafting an audience-safe package. Another cleared lawyer must approve release; clean-team output also needs separate antitrust approval.\n\nImage-only PDFs remain OCR-required until an OCR adapter is configured. Never interpret missing text as completed review. L002 prohibits AI processing and must remain human-review only. All parties, clauses and amounts are fictional; examples are not legal research.\n',encoding='utf-8')
print('Two local manifests finalized: Wave 1 five files; Wave 2 six files retained for manual processing.')
