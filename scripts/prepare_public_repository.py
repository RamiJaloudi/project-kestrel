"""Create a new, allowlisted publication tree. Never copies local Git history.

Run with --destination to a new directory outside this source tree. Review the
manifest and scan findings before publishing. This script never sends data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('backend','frontend','data','deployment','docs','scripts','fixtures','synthetic','diagrams','deliverables')
SKIP_DIRS = {'.git','.runtime','.venv','node_modules','dist','__pycache__','.pytest_cache','.mypy_cache',
             '.ruff_cache','.cache','tmp','output','outputs','uploads','secrets','credentials','coverage','archive'}
SKIP_EXTENSIONS = {'.pyc','.pyo','.db','.sqlite','.sqlite3','.log','.key','.pem','.pfx','.p12','.exe','.dll','.whl','.zip','.tsbuildinfo'}
ROOT_FILES = ('.gitattributes','.gitignore','.env.example','.env.azure.example','AGENTS.md','CREATE_ACCOUNT.bat',
              'START_KESTREL.bat','STOP_KESTREL.bat','STATUS_KESTREL.bat','docs/08_development/MASTER_CODEX_PROMPT.md')
TOKEN_PATTERNS = [
    ('OpenAI key',re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}')),
    ('GitHub token',re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})')),
    ('AWS access key',re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('Private key',re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
    ('Google API key',re.compile(rb'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('Credentialed DB URL',re.compile(rb'postgres(?:ql)?(?:\+[a-z]+)?://[^\s/:]+:([^\s@]+)@')),
]


def permitted(path, base):
    rel=path.relative_to(base)
    if any(part.lower() in SKIP_DIRS or part.endswith('.egg-info') for part in rel.parts): return False
    if path.is_symlink() or not path.is_file(): return False
    curated_bundle = path.name=='Presentation_and_Companions.zip' and path.parent.name=='resource_library'
    if (path.suffix.lower() in SKIP_EXTENSIONS and not curated_bundle) or path.name.startswith(('~$','.~')): return False
    if path.name.startswith('.env') and path.name not in {'.env.example','.env.azure.example'}: return False
    if path.name.lower() in {'demo-accounts.json','credential-export.json','database.json','ai-provider.json'}: return False
    return True


def extract_scan_units(path):
    if path.suffix.lower() in {'.docx','.xlsx','.pptx'}:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith(('.xml','.rels')): yield name,archive.read(name)
    else:
        yield '',path.read_bytes()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--destination',required=True);args=parser.parse_args()
    destination=Path(args.destination).resolve()
    if destination==ROOT or ROOT in destination.parents: raise SystemExit('Destination must be outside the source tree')
    if destination.exists() and any(destination.iterdir()): raise SystemExit('Destination must be new or empty')
    destination.mkdir(parents=True,exist_ok=True)
    copied=[]
    def copy(source,target):
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);copied.append(target)
    for directory in DIRECTORIES:
        base=ROOT/directory
        for folder, names, files in os.walk(base,followlinks=False):
            names[:]=[name for name in names if name.lower() not in SKIP_DIRS and not name.endswith('.egg-info')]
            for filename in files:
                path=Path(folder)/filename
                if permitted(path,base):copy(path,destination/path.relative_to(ROOT))
    for filename in ROOT_FILES:
        if (ROOT/filename).is_file():copy(ROOT/filename,destination/filename)
    # The topic-organized setup guide is already included by the docs copy.

    # Authored deliverables only, not the supplied reference-input folder or notes.
    authored=ROOT.parent/'Deliverables/Project_Kestrel_Written_Deliverables_2026-11-24'
    for directory in ['01_Presentation','02_Partner_Note','03_DDR_Checklist','04_VDR_Tracker','05_Schema','06_Panel_Preparation','08_Tech_Stack_and_Schema']:
        for path in (authored/directory).rglob('*'):
            if not permitted(path,authored):continue
            if path.name in {'Project_Kestrel_Freshfields_REVIEW_v2.pptx','README.txt'}:continue
            copy(path,destination/'deliverables'/path.relative_to(authored))
    shutil.copyfile(ROOT/'README.md', destination/'README.md')
    # Adjust public working instructions so omitted originals are not a hidden prerequisite.
    agents=destination/'AGENTS.md'
    text=agents.read_text(encoding='utf-8')
    text=text.replace('1. `source/Legal Solutions Architect - Assessment Brief.docx` (5 pages, authoritative), the JD only for technology expectations.',
                      '1. This public snapshot intentionally omits supplied third-party original briefs and forms. Read `docs/01_design/00_SOURCE_AND_SCOPE.md` for the recorded scope; obtain authorized originals separately if required for source verification.')
    agents.write_text(text,encoding='utf-8')
    with (destination/'.gitignore').open('a',encoding='utf-8') as stream:
        stream.write('\n# Private runtime state and publication junk\nCredentials/\ncredentials/\n*.pfx\n*.p12\n*.sqlite\n*.sqlite3\n*.zip\n!backend/kestrel/data/resource_library/Presentation_and_Companions.zip\ntmp/\noutput/\n~$*\n')
    findings=[]
    for path in destination.rglob('*'):
        if not path.is_file():continue
        for member,data in extract_scan_units(path):
            for kind,pattern in TOKEN_PATTERNS:
                if pattern.search(data): findings.append({'file':path.relative_to(destination).as_posix(),'member':member,'kind':kind})
    manifest=[{'file':p.relative_to(destination).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in sorted(destination.rglob('*')) if p.is_file()]
    report={'files':len(manifest),'bytes':sum(item['bytes'] for item in manifest),
            'contains_local_git_history':False,'scan_findings':findings,
            'exclusions':['private environment and credentials','runtime state and database backups','third-party supplied originals',
                          'private notes and external chats','generated caches and dependency installs','duplicate old project copies','old presentation v2'],
            'manifest':manifest}
    report_path=destination.parent/'PUBLICATION_REVIEW.json'
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['files','bytes','contains_local_git_history','scan_findings']},indent=2))


if __name__=='__main__':main()
