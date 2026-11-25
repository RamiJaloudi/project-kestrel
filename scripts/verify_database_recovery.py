"""Explicit local logical backup/restore check; never restore over the active database."""
import argparse,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from sqlalchemy import inspect,text
from sqlalchemy.engine import make_url
from kestrel.database import database_url,make_engine
from kestrel.adapters.provider_secrets import crypt
from kestrel.diagnostics import emit

def normalized(value):
    if isinstance(value,(bytes,bytearray,memoryview)):return {'byte_count':len(value),'sha256':hashlib.sha256(value).hexdigest()}
    if value is None or isinstance(value,(str,int,float,bool)):return value
    return str(value)

def inventory(connection):
    result={};quote=connection.dialect.identifier_preparer.quote
    for table in sorted(inspect(connection).get_table_names(schema='public')):
        hashes=[]
        for row in connection.execute(text('SELECT * FROM public.'+quote(table))).mappings():
            hashes.append(hashlib.sha256(json.dumps({k:normalized(v) for k,v in row.items()},sort_keys=True,separators=(',',':')).encode()).hexdigest())
            if len(hashes)>100000:raise RuntimeError('Bounded local recovery check exceeded row limit')
        result[table]={'rows':len(hashes),'sha256':hashlib.sha256(''.join(sorted(hashes)).encode()).hexdigest()}
    return result

def normalized_constraint(value):
    """PG restore may distribute text[] casts over a fixed varchar literal array.

    Normalize only that exact constant form. Never erase arbitrary expressions,
    varchar lengths, values, ordering, operators or other constraint semantics.
    """
    literal=r"'(?:[^']|'')*'::character varying"
    pattern=r"\(ARRAY\[((?:"+literal+r")(?:, "+literal+r")*)\]\)::text\[\]"
    return re.sub(pattern,lambda match:'ARRAY['+', '.join('('+token+')::text' for token in re.findall(literal,match.group(1)))+']',value)

def constraints(connection):
    return {row[0]+'.'+row[1]:normalized_constraint(row[2]) for row in connection.execute(text("SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON k.conrelid=c.oid JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public' ORDER BY c.relname,k.conname"))}

def structure(connection):
    queries={
        'views':"SELECT viewname, definition FROM pg_views WHERE schemaname='public' ORDER BY viewname",
        'functions':"SELECT p.proname, pg_get_function_identity_arguments(p.oid), pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)",
        'triggers':"SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON t.tgrelid=c.oid JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname",
        'constraints':"SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON k.conrelid=c.oid JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public' ORDER BY c.relname,k.conname",
        'indexes':"SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname"}
    result={}
    for kind,sql in queries.items():
        rows=[list(row) for row in connection.execute(text(sql))]
        if kind=='constraints':
            for row in rows:row[2]=normalized_constraint(row[2])
        result[kind]=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:raise RuntimeError('Explicit --execute required')
    url=make_url(database_url())
    if url.get_backend_name()!='postgresql' or url.host not in {'127.0.0.1','localhost','::1'}:raise RuntimeError('Only local PostgreSQL recovery verification is permitted')
    binary=Path('C:/Program Files/PostgreSQL/18/bin');environment={**os.environ,'PGPASSWORD':url.password or '','PGCONNECT_TIMEOUT':'10'}
    common=['--host',url.host,'--port',str(url.port or 5432),'--username',url.username]
    engine=make_engine(url.render_as_string(hide_password=False));scratch='kestrel_recovery_'+uuid4().hex
    if not re.fullmatch(r'kestrel_recovery_[a-f0-9]{32}',scratch) or scratch==url.database:raise RuntimeError('Scratch database identity rejected')
    created=False;restored_engine=None;started=time.time()
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as source:
            with source.begin():
                source.execute(text('SET TRANSACTION READ ONLY'))
                snapshot=source.scalar(text('SELECT pg_export_snapshot()'))
                expected=inventory(source);expected_structure=structure(source);expected_constraints=constraints(source)
                dump=subprocess.run([str(binary/'pg_dump.exe'),*common,'--dbname',url.database,'--format=custom','--no-owner','--no-acl','--schema=public','--lock-wait-timeout=10s','--snapshot',snapshot],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
                if dump.returncode or not dump.stdout.startswith(b'PGDMP') or len(dump.stdout)>50*1024*1024:raise RuntimeError('Bounded PostgreSQL dump failed')
        directory=ROOT/'.runtime/database-backups';directory.mkdir(parents=True,exist_ok=True);key=uuid4().hex
        protected=crypt(dump.stdout,True);target=directory/(key+'.dpapi')
        with target.open('xb') as output:output.write(protected);output.flush();os.fsync(output.fileno())
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as admin:
            admin.execute(text('CREATE DATABASE "'+scratch+'"'));created=True
        recovered=crypt(target.read_bytes(),False)
        if hashlib.sha256(recovered).digest()!=hashlib.sha256(dump.stdout).digest():raise RuntimeError('Backup decryption integrity mismatch')
        restore=subprocess.run([str(binary/'pg_restore.exe'),*common,'--dbname',scratch,'--clean','--if-exists','--exit-on-error','--no-owner','--no-acl'],input=recovered,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        if restore.returncode:
            with (directory/(key+'.incident.dpapi')).open('xb') as evidence:evidence.write(crypt(restore.stderr,True))
            print(json.dumps({'restore_failed':True,'schema_already_exists':b'already exists' in restore.stderr,'permission_denied':b'permission denied' in restore.stderr,'restricted_incident_retained':True}),flush=True)
            raise RuntimeError('Scratch restore failed; restricted diagnostics retained')
        restored_engine=make_engine(url.set(database=scratch).render_as_string(hide_password=False))
        with restored_engine.connect() as destination:actual=inventory(destination);actual_structure=structure(destination);actual_constraints=constraints(destination)
        if expected!=actual or expected_structure!=actual_structure:
            print(json.dumps({'data_tables_differ':[k for k in expected if expected.get(k)!=actual.get(k)],'schema_sections_differ':[k for k in expected_structure if expected_structure.get(k)!=actual_structure.get(k)]}),flush=True)
            if expected_constraints!=actual_constraints:
                keys=sorted(set(expected_constraints)|set(actual_constraints))
                differences=[{'name':k,'source_definition':expected_constraints.get(k),'restored_definition':actual_constraints.get(k)} for k in keys if expected_constraints.get(k)!=actual_constraints.get(k)]
                with (directory/(key+'.schema-incident.dpapi')).open('xb') as evidence:evidence.write(crypt(json.dumps(differences).encode(),True))
                print(json.dumps({'constraint_mismatch':True,'restricted_schema_evidence_retained':True}),flush=True)
            raise RuntimeError('Restored row counts or content digests differ')
        report={'schema':'kestrel-local-database-recovery-1','verified_at':int(time.time()),'tables':expected,'schema_digests':expected_structure,'backup_sha256':hashlib.sha256(protected).hexdigest(),'logical_dump_sha256':hashlib.sha256(recovered).hexdigest(),'verified':True,'encrypted_for_current_windows_user':True,'worm':False,'runtime_files_included':False,'duration_seconds':round(time.time()-started,2)}
        (directory/(key+'.manifest.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        summary={'verified':True,'tables':len(expected),'rows':sum(t['rows'] for t in expected.values()),'duration_seconds':report['duration_seconds'],'encrypted_backup_retained':True,'scratch_removed_on_exit':True,'runtime_files_included':False,'schema_verified':True}
    finally:
        if restored_engine:restored_engine.dispose()
        if created:
            # This generated identity is checked above and never derives from a user path/name.
            with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as admin:admin.execute(text('DROP DATABASE "'+scratch+'" WITH (FORCE)'))
        engine.dispose()
    print(json.dumps(summary),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        event=emit('database.recovery_check_failed',component='verification',exception=error)
        print('Database recovery check failed; sanitized diagnostic '+event['event_id']);sys.exit(1)
