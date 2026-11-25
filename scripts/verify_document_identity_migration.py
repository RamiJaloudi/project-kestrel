"""Rehearse 0026/0027 on a restored copy; --target selects the approved increment.

Never restores over the active database; manifests expose counts/digests only.
"""
import argparse,hashlib,importlib.util,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from sqlalchemy import text
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from kestrel.database import database_url,make_engine
from kestrel.adapters.provider_secrets import crypt
from verify_database_recovery import inventory


def verify(engine,before):
    with engine.begin() as c:
        after=inventory(c)
        changed=[t for t in before if t!='alembic_version' and before[t]!=after.get(t)]
        if changed:raise RuntimeError('Existing table digests changed during additive migration')
        if c.scalar(text('SELECT count(*) FROM source_versions s LEFT JOIN document_version_links l ON l.source_id=s.id LEFT JOIN documents d ON d.id=l.document_id WHERE l.source_id IS NULL OR s.matter_id<>l.matter_id OR s.bytes_hash<>l.bytes_hash OR d.matter_id<>s.matter_id OR d.logical_key<>s.logical_key')):raise RuntimeError('Invalid identity projection')
        p=ROOT/'backend/migrations/versions/0026_document_identity_vdr.py';spec=importlib.util.spec_from_file_location('vdr_migration',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        counts={t:after[t] for t in ['documents','document_version_links']}
        module.backfill(c);module.backfill(c)
        twice=inventory(c)
        if any(twice[t]!=counts[t] for t in counts):raise RuntimeError('Backfill replay changed identity records')
        if c.scalar(text('SELECT version_num FROM alembic_version')) in {'0029','0030','0031','0032','0033','0034','0035','0036','0037','0038'}:
            from kestrel.migration_support.checklist_projection_v1 import backfill
            backfill(c);backfill(c)
            if inventory(c)!=twice:raise RuntimeError('Checklist backfill replay changed retained records')
        return {'head':c.scalar(text('SELECT version_num FROM alembic_version')),'existing_tables_preserved':len(before)-1,
            'source_versions':after['source_versions']['rows'],'logical_documents':after['documents']['rows'],
            'version_links':after['document_version_links']['rows'],'fk_orphans':0,'backfill_replayed_twice':True,'old_table_digests':before}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--target',choices=['0026','0027','0028','0029','0030','0031','0032','0033','0034','0035','0036','0037','0038'],default='0026');args=parser.parse_args()
    target=args.target;previous={'0026':'0025','0027':'0026','0028':'0027','0029':'0028','0030':'0029','0031':'0030','0032':'0031','0033':'0032','0034':'0033','0035':'0034','0036':'0035','0037':'0036','0038':'0037'}[target];prefix={'0026':'vdr','0027':'review-work','0028':'review-clocks','0029':'gate1-completion','0030':'content-labels','0031':'disclosures','0032':'retrieval','0033':'financial','0034':'saved-views','0035':'intelligence','0036':'ddr','0037':'agent-registry','0038':'financial-context'}[target]
    migration=ROOT/'backend/migrations/versions'/({'0026':'0026_document_identity_vdr.py','0027':'0027_custodians_review_tasks.py','0028':'0028_review_clocks_sla.py','0029':'0029_checklist_records_sla_alerts.py','0030':'0030_content_labels.py','0031':'0031_validated_disclosures.py','0032':'0032_source_embeddings.py','0033':'0033_financial_facts.py','0034':'0034_saved_table_views.py','0035':'0035_intelligence_governance.py','0036':'0036_ddr_runs.py','0037':'0037_agent_registry.py','0038':'0038_financial_context.py'}[target])
    migration_hash=hashlib.sha256(migration.read_bytes()).hexdigest()
    url=make_url(database_url())
    if url.get_backend_name()!='postgresql' or url.host not in {'127.0.0.1','localhost','::1'}:raise RuntimeError('Local PostgreSQL required')
    active=make_engine(url.render_as_string(hide_password=False));cfg=Config(str(ROOT/'backend/alembic.ini'))
    out=ROOT/'.runtime/prompt-audit';out.mkdir(exist_ok=True,parents=True)
    if args.apply:
        receipt=json.loads((out/(prefix+'-migration-rehearsal.json')).read_text())
        if not receipt.get('verified') or receipt['head']!=target or receipt.get('migration_sha256')!=migration_hash:raise RuntimeError('Successful rehearsal required')
        with active.connect() as c:
            if c.scalar(text('SELECT version_num FROM alembic_version'))!=previous:raise RuntimeError('Unexpected live migration head')
            before=inventory(c)
        command.upgrade(cfg,target);result=verify(active,before);result['migration_sha256']=migration_hash
        (out/(prefix+'-migration-applied.json')).write_text(json.dumps({'verified':True,**result},indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in result.items() if k!='old_table_digests'}));return
    manifests=sorted((ROOT/'.runtime/database-backups').glob('*.manifest.json'),key=lambda p:p.stat().st_mtime)
    if not manifests:raise RuntimeError('Restore-verified encrypted backup required')
    manifest=manifests[-1];backup=manifest.with_name(manifest.name.replace('.manifest.json','.dpapi'))
    prior=json.loads(manifest.read_text())
    if not prior.get('verified'):raise RuntimeError('Backup not verified')
    scratch='kestrel_vdr_'+uuid4().hex
    if not re.fullmatch(r'kestrel_vdr_[a-f0-9]{32}',scratch):raise RuntimeError('Invalid scratch identity')
    created=False;copy=None;old=os.environ.get('KESTREL_DATABASE_URL')
    try:
        with active.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE "'+scratch+'"'));created=True
        env={**os.environ,'PGPASSWORD':url.password or '','PGCONNECT_TIMEOUT':'10'}
        restore=subprocess.run(['C:/Program Files/PostgreSQL/18/bin/pg_restore.exe','--host',url.host,'--port',str(url.port),'--username',url.username,'--dbname',scratch,'--clean','--if-exists','--exit-on-error','--no-owner','--no-acl'],input=crypt(backup.read_bytes(),False),capture_output=True,env=env,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        if restore.returncode:raise RuntimeError('Scratch restore failed')
        target_connection=url.set(database=scratch).render_as_string(hide_password=False);copy=make_engine(target_connection)
        with copy.connect() as c:
            before=inventory(c)
            if before!=prior['tables']:raise RuntimeError('Restored backup differs from its verified manifest')
            if c.scalar(text('SELECT version_num FROM alembic_version'))!=previous:raise RuntimeError('Unexpected restored migration head')
        os.environ['KESTREL_DATABASE_URL']=target_connection
        command.upgrade(cfg,target);command.upgrade(cfg,target)
        result=verify(copy,before);result['verified']=True;result['migration_sha256']=migration_hash
        (out/(prefix+'-migration-rehearsal.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in result.items() if k!='old_table_digests'}))
    finally:
        if old is None:os.environ.pop('KESTREL_DATABASE_URL',None)
        else:os.environ['KESTREL_DATABASE_URL']=old
        if copy:copy.dispose()
        if created:
            with active.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE "'+scratch+'" WITH (FORCE)'))
        active.dispose()


if __name__=='__main__':
    try:main()
    except Exception:
        print('Identity migration verification failed; no diagnostic values or connection credentials printed.');sys.exit(1)
