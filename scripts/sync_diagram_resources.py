"""Copy canonical diagrams into the packaged authenticated library.

The repo diagrams folder is the authoring source. Existing six download IDs
remain stable. Extra diagram downloads use their numbered canonical filenames.
"""
import hashlib
import json
from pathlib import Path
import shutil
import os

ROOT=Path(__file__).resolve().parents[1]
ALIASES={'Azure_Deployment':'03_azure_dns_and_deployment','API_Architecture':'04_api_architecture',
         'Document_to_Report':'06_document_evidence_lifecycle','Search_Architecture':'07_permission_first_search',
         'Access_and_Release':'12_access_and_audience_boundaries','Schema_Story':'16_the_data_story'}


def sync(root=ROOT):
    source=root/'diagrams';library=root/'backend/kestrel/data/resource_library'
    if not source.is_dir():source=root.parent/'Diagrams'
    catalogue_path=library/'catalog.json'
    if not (source/'catalog.json').is_file():return
    diagrams=json.loads((source/'catalog.json').read_text(encoding='utf-8'))['diagrams']
    catalogue=json.loads(catalogue_path.read_text(encoding='utf-8'))
    by_id={entry['id']:entry for entry in diagrams}
    assets=[entry for entry in catalogue['assets'] if entry['category']!='Diagrams']
    names={value:key for key,value in ALIASES.items()}
    for entry in diagrams:
        stem=names.get(entry['id'],entry['id'])
        for extension,mime in [('svg','image/svg+xml'),('mmd','text/plain'),('png','image/png')]:
            original=source/entry['folder']/(entry['id']+'.'+extension)
            if not original.is_file():continue
            filename=stem+'.'+extension;target=library/filename;shutil.copyfile(original,target)
            assets.append({'id':stem.lower().replace('_','-')+'-'+extension,'filename':filename,
                'title':entry['title']+(' editable source' if extension=='mmd' else ' image' if extension=='png' else ''),
                'description':entry['note'],'category':'Diagrams','audiences':['firm','halden','castlegate'],
                'status':entry['status'],'media_type':mime,'bytes':target.stat().st_size,
                'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'updated':'2026-11-24'})
    assert len({entry['id'] for entry in assets})==len(assets)
    active_files={entry['filename'] for entry in assets}
    for previous in catalogue['assets']:
        if previous['category']=='Diagrams' and previous['filename'] not in active_files:
            obsolete=library/previous['filename']
            if obsolete.name==previous['filename'] and obsolete.resolve().parent==library.resolve() and obsolete.is_file():obsolete.unlink()
    catalogue['assets']=assets;catalogue_path.write_text(json.dumps(catalogue,indent=2),encoding='utf-8')
    guide=root/'docs/resources/README.md';guide.parent.mkdir(parents=True,exist_ok=True)
    diagram_link=Path(os.path.relpath(source,guide.parent)).as_posix()+'/README.md'
    lines=['# Resource library','', f'[Architecture diagram library]({diagram_link}) · [Guides by topic](../README.md) · [Written deliverables](../../deliverables/README.md)','',
           'Portal downloads require sign-in and current organization eligibility. These public repository files are authored documentation and synthetic examples. Diagrams are authored in the single top-level diagrams folder; the copies under the backend are generated application download assets.','']
    for category in dict.fromkeys(entry['category'] for entry in assets):
        lines+=['## '+category,'']
        if category=='Diagrams':
            lines+=[f'[Browse all architecture and data diagrams together]({diagram_link}). Use SVG for a scalable picture, PNG for slides and Mermaid for editing.',''];continue
        for entry in assets:
            if entry['category']==category:lines.append(f'- [{entry["title"]}](../../backend/kestrel/data/resource_library/{entry["filename"]}) — {entry["description"]}')
        lines+=['']
    guide.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    return len(assets)


if __name__=='__main__':print(json.dumps({'resource_assets':sync()}))
