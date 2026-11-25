"""Allowlisted local review bundle; no deployment, database access or deletion.

Default is a review plan. --build requires a current verified full-suite receipt.
All runtime state, backups, credentials, QA databases and prior bundles stay local.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime,timezone
from uuid import uuid4
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_HEAD='0038'
DECK='Project_Kestrel_Freshfields_REVIEW_v2.pptx'
DECK_HASH='cc52cfc05ba2c8e14c76eee89e37ba37c696dae54b342d4860aef20c46225b82'
NOTES=ROOT/'delivery/submission_20261124'
PRESENTATION=ROOT/'delivery/panel_presentation/OUTPUT'
BLOCKED_PARTS={'.runtime','.venv','node_modules','.git','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','dist','_qa','qa','qafixture','qa_fixture','secrets','uploads','tmp','agent_profile_drafts'}
BLOCKED_SUFFIXES={'.db','.sqlite','.sqlite3','.dpapi','.log','.pem','.key','.pfx','.p12','.cer','.crt','.pyc','.pyo','.dmp','.dump','.bak','.tmp','.tsbuildinfo'}
TEXT_SUFFIXES={'.py','.js','.mjs','.ts','.tsx','.css','.svg','.json','.md','.txt','.ps1','.bat','.ini','.toml','.lock','.html','.mako','.bicep','.example'}
SECRETS=[re.compile(rb'sk-(?:proj|svcacct)-[A-Za-z0-9_-]{40,}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----')]


def digest(data):return hashlib.sha256(data).hexdigest()


def checked_path(path):
    resolved=path.resolve(strict=True)
    if not resolved.is_relative_to(ROOT) or path.is_symlink():raise ValueError('Bundle input is outside the project or is a symbolic link')
    relative=resolved.relative_to(ROOT)
    if any(part.casefold() in BLOCKED_PARTS for part in relative.parts) or resolved.suffix.casefold() in BLOCKED_SUFFIXES:raise ValueError('Forbidden bundle input: '+str(relative))
    name=resolved.name.casefold()
    if name.startswith('.env') and name not in {'.env.example','.env.azure.example'}:raise ValueError('Private environment input rejected')
    template=relative.parts[:4]==('backend','kestrel','data','workflow_scripts')
    if not template and resolved.suffix.casefold() in {'.csv','.json','.txt','.xlsx'} and any(word in name for word in ['credential','owner-approval','public-approval','submitted_review_receipt','demo-accounts']):raise ValueError('Private credential/approval artifact rejected: '+str(relative))
    return resolved


def candidates():
    selected={}
    def add(path,group):
        path=checked_path(path)
        if path.is_file():selected[path]=group
    roots=[('backend/kestrel',{'.py','.js','.json','.xlsx'},'application'),('backend/migrations',{'.py','.mako'},'migration-source'),
        ('backend/tests',{'.py'},'test-source'),('frontend/src',{'.ts','.tsx','.css','.svg','.png','.jpg','.jpeg','.webp','.ico'},'frontend-source'),
        ('frontend/public',{'.svg','.png','.jpg','.jpeg','.webp','.ico','.txt'},'frontend-source'),
        ('docs',{'.md','.mmd','.json'},'implementation-evidence'),('prompts',{'.md','.json'},'design-context'),
        ('scripts',{'.py','.ps1','.mjs','.json'},'operator-source'),('data',{'.json','.md','.txt','.pdf','.docx','.xlsx'},'synthetic-source'),
        ('fixtures/wave2',{'.txt','.json'},'synthetic-exercise')]
    for directory,suffixes,group in roots:
        base=ROOT/directory
        if not base.exists():continue
        for path in base.rglob('*'):
            if path.is_file() and path.name!='serve_registry_browser_fixture.py' and path.suffix.casefold() in suffixes and not any(part.casefold() in BLOCKED_PARTS for part in path.relative_to(ROOT).parts):add(path,group)
    for relative in ['README.md','AGENTS.md','.gitignore','.env.example','.env.azure.example','START_KESTREL.bat','STOP_KESTREL.bat','STATUS_KESTREL.bat','CREATE_ACCOUNT.bat',
        'backend/alembic.ini','backend/pyproject.toml','backend/requirements-tested.txt','backend/requirements-ddr.lock','backend/README.md',
        'frontend/package.json','frontend/package-lock.json','frontend/tsconfig.json','frontend/vite.config.ts','frontend/index.html','frontend/README.md','frontend/THIRD_PARTY_NOTICES.md',
        'frontend/src/playbook-starter.json','frontend/scripts/copy-swagger.mjs',
        'deployment/Caddyfile.public.example','deployment/azure/README.md','deployment/azure/Review-Plan.ps1','deployment/azure/main.bicep','deployment/azure/main.json','deployment/azure/parameters.example.json',
        'source/Legal Solutions Architect - Assessment Brief.docx','source/AI Solution Architect (1)(2).docx',
        'delivery/assessment/Project_Kestrel_Partner_Note_DRAFT.pdf','delivery/assessment/Project_Kestrel_Partner_Note_DRAFT.txt']:
        add(ROOT/relative,'reviewed-root-artifact')
    for name in ['README.md','IMPLEMENTATION_CHECKPOINT.md','CORE_FLOW_CHECKLIST.md','AI_ASSISTANCE_DISCLOSURE.md','BUILD_AND_MIGRATION_CHECKLIST.md','manifest.json','RESOURCE_GUIDANCE_CHECKS.json','FINAL_VERIFICATION.json']:add(NOTES/name,'current-submission-notes')
    package=json.loads((PRESENTATION/'PACKAGE_MANIFEST.json').read_text(encoding='utf8'))
    if package.get('pptx_sha256')!=DECK_HASH:raise ValueError('Approved v2 presentation manifest changed; obtain a new reviewed selection')
    for entry in package['files']:
        relative=Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or not (entry['path'] in {DECK,'README.txt'} or relative.parts[0]=='companions'):raise ValueError('Unexpected presentation companion')
        path=checked_path(PRESENTATION/relative)
        if digest(path.read_bytes())!=entry['sha256']:raise ValueError('Presentation companion differs from its reviewed manifest')
        add(path,'approved-v2-presentation')
    if digest((PRESENTATION/DECK).read_bytes())!=DECK_HASH:raise ValueError('Approved v2 presentation bytes changed')
    add(PRESENTATION/'PACKAGE_MANIFEST.json','approved-v2-presentation')
    verify_frontend_inputs(selected)
    return selected


def verify_frontend_inputs(selected):
    """Refuse a source package missing authored relative imports/build helpers.

    JSON remains explicitly reviewed above; this check never broadens the input
    allowlist to include arbitrary frontend JSON or operational state.
    """
    available={path.resolve() for path in selected}
    frontend=(ROOT/'frontend').resolve()
    dependencies=[]
    pattern=re.compile(r'''(?:\bfrom\s*|\bimport\s*(?:\(\s*)?)["'](\.[^"']+)["']|\burl\(\s*["']?(\.[^\s)'"?]+)''')
    for source in sorted(available):
        if not source.is_relative_to(frontend/'src') or source.suffix not in {'.ts','.tsx','.css'}:continue
        for match in pattern.finditer(source.read_text(encoding='utf8')):
            raw=next(value for value in match.groups() if value).split('?',1)[0].split('#',1)[0]
            base=(source.parent/raw).resolve()
            choices=[base] if base.suffix else [base.with_suffix(suffix) for suffix in ['.ts','.tsx','.js','.json','.css']]+[base/'index.ts',base/'index.tsx']
            target=next((path for path in choices if path.is_file()),None)
            if target is None or not target.is_relative_to(frontend) or target not in available:
                raise ValueError('Required frontend import omitted from reviewed package: '+str(source.relative_to(ROOT))+' -> '+raw)
            dependencies.append(target.relative_to(ROOT).as_posix())
    package=json.loads((frontend/'package.json').read_text(encoding='utf8'))
    for helper in re.findall(r'\bnode\s+(scripts/[A-Za-z0-9_./-]+)',package.get('scripts',{}).get('build','')):
        path=(frontend/helper).resolve()
        if not path.is_relative_to(frontend) or path not in available:raise ValueError('Required frontend build helper omitted: '+helper)
        dependencies.append(path.relative_to(ROOT).as_posix())
    return sorted(set(dependencies))


def migration_receipt():
    revisions={};files=[]
    for path in sorted((ROOT/'backend/migrations/versions').glob('*.py')):
        values={}
        for node in ast.parse(path.read_text(encoding='utf-8-sig')).body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Name) and target.id in {'revision','down_revision'}:values[target.id]=ast.literal_eval(node.value)
        if 'revision' not in values:continue
        if values['revision'] in revisions:raise ValueError('Duplicate migration revision')
        revisions[values['revision']]=values['down_revision']
        files.append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path.read_bytes()),**values})
    parents={value for value in revisions.values() if value is not None}
    heads=set(revisions)-parents
    if heads!={EXPECTED_HEAD} or any(parent is not None and parent not in revisions for parent in revisions.values()):raise ValueError('Unexpected or incomplete migration chain')
    seen=set();current=EXPECTED_HEAD
    while current is not None:
        if current in seen:raise ValueError('Migration cycle')
        seen.add(current);current=revisions[current]
    if seen!=set(revisions):raise ValueError('Disconnected migration source')
    return {'head':EXPECTED_HEAD,'revision_count':len(revisions),'source_only':True,'applied_or_rehearsed_by_this_builder':False,'files':files}


def regression_receipt(path):
    if path is None:return {'current_full_suite':'pending; --build disabled without a verified receipt'}
    path=path.resolve(strict=True)
    if not path.is_relative_to(ROOT/'.runtime/test-runs') or path.name!='result.json':raise ValueError('Expected the retained local full-suite result.json')
    result=json.loads(path.read_text(encoding='utf8'))
    frozen=json.loads((path.parent/'source-hashes.json').read_text(encoding='utf8'))
    from run_sqlite_regression import source_hashes
    if not result.get('verified') or not result.get('source_unchanged') or frozen!=source_hashes():raise ValueError('Full-suite receipt is not verified for current source')
    if not result.get('shards') or any(row['exit_code']!=0 or row['executed']!=row['expected'] for row in result['shards']):raise ValueError('Full-suite accounting incomplete')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true',help='Write and reverify a local ZIP; does not deploy or transfer it')
    parser.add_argument('--regression-result',type=Path,help='Current verified .runtime/test-runs/.../result.json')
    args=parser.parse_args()
    if args.build and args.regression_result is None:parser.error('--build requires the final current --regression-result')
    if args.build:
        acceptance=json.loads((NOTES/'FINAL_VERIFICATION.json').read_text(encoding='utf8'))
        if acceptance.get('automated_regression_verified') is not True or acceptance.get('full_sqlite_result_sha256')!=digest(args.regression_result.read_bytes()):raise ValueError('Final automated verification receipt is pending or does not match the supplied run')
    from verify_workflow_scripts import verify
    templates=verify();selected=candidates();entries=[];total=0
    for path,group in sorted(selected.items()):
        data=path.read_bytes();total+=len(data)
        if len(data)>32*1024*1024 or total>256*1024*1024:raise ValueError('Bounded source bundle size exceeded')
        if path.suffix.casefold() in TEXT_SUFFIXES and any(pattern.search(data) for pattern in SECRETS):raise ValueError('Potential private key found; inspect locally: '+str(path.relative_to(ROOT)))
        entries.append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest(data),'bytes':len(data),'group':group})
    manifest={'schema':'kestrel-local-review-source-bundle-1','created_at':datetime.now(timezone.utc).isoformat(),
        'purpose':'Local review/submission source and approved assessment artifacts; not a data migration or public approval',
        'files':entries,'source_bytes':total,'workflow_templates_verified':templates,'migrations':migration_receipt(),'sqlite_regression':regression_receipt(args.regression_result),
        'excluded_and_retained_locally':['.runtime and all database/backup/checkpoint/log/session state','.env and credential exports','virtual environments and node_modules','QA fixtures/build caches','submitted profile receipts and public approval records','obsolete scaffold delivery status and older presentation bundles'],
        'database_included':False,'credentials_included':False,'data_migration_performed':False,'public_deployment_authorized':False,
        'all_expanded_gates_complete':False,'manual_or_legal_acceptance_claimed':False,'paid_provider_acceptance_claimed':False}
    output=ROOT/'delivery/submission_bundles'/uuid4().hex;output.mkdir(parents=True,exist_ok=False)
    manifest_path=output/'SUBMISSION_MANIFEST.json';manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf8')
    result={'plan':not args.build,'files':len(entries),'bytes':total,'migration_head':EXPECTED_HEAD,'templates':templates,'directory':str(output.relative_to(ROOT)),'source_retained':True,'deployed':False}
    if args.build:
        archive_path=output/'Project_Kestrel_review_source.zip'
        with ZipFile(archive_path,'x',ZIP_DEFLATED) as archive:
            for entry in entries:
                data=(ROOT/entry['path']).read_bytes()
                if digest(data)!=entry['sha256']:raise ValueError('Source changed after manifest; archive retained as incomplete')
                archive.writestr(entry['path'],data)
            archive.writestr('SUBMISSION_MANIFEST.json',manifest_path.read_bytes())
        with ZipFile(archive_path) as archive:
            if archive.testzip() is not None or set(archive.namelist())!={entry['path'] for entry in entries}|{'SUBMISSION_MANIFEST.json'}:raise ValueError('Archive verification failed')
            if any(digest(archive.read(entry['path']))!=entry['sha256'] for entry in entries):raise ValueError('Archive content digest mismatch')
        if any(digest((ROOT/entry['path']).read_bytes())!=entry['sha256'] for entry in entries):raise ValueError('Source changed while bundling; retain this incomplete attempt and rebuild after review')
        result.update(archive_sha256=digest(archive_path.read_bytes()),archive=str(archive_path.relative_to(ROOT)),archive_verified=True)
    (output/'BUILD_RECEIPT.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
