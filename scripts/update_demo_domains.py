"""Explicit operator migration; keeps account IDs and all scoped references."""
import json
from pathlib import Path
import sys
import time
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env
from kestrel.database import make_engine,database_url,factory
from kestrel.demo_directory import rename_accounts,credential_rows
from kestrel.demo_names import NAMED
from kestrel.demo_setup import setup,setup_owner
from local_certificate import protect

def main():
    values=read_env()
    backup=root/'.runtime'/('identity-settings-'+str(int(time.time()))+'.env')
    backup.write_bytes((root/'.env').read_bytes());protect(backup)
    with factory(make_engine(database_url()))() as db:
        renamed=rename_accounts(db,values)
        rows=setup(db,values['KESTREL_DUMMY_PASSWORD'])
        setup_owner(db,values['KESTREL_DUMMY_PASSWORD'],NAMED['KESTREL_RAMI_EMAIL'])
        db.commit()
        values.update(NAMED)
        directory=credential_rows(db,values)
        if len(directory)!=36:raise ValueError('Unexpected account count; review before export')
    (root/'.env').write_text('# Local synthetic demo settings\n'+'\n'.join(k+'='+json.dumps(v) for k,v in values.items())+'\n',encoding='utf-8');protect(root/'.env')
    (root/'.runtime/demo-accounts.json').write_text(json.dumps({'accounts':rows,'password_env_key':'KESTREL_DUMMY_PASSWORD'},indent=2),encoding='utf-8')
    source=root/'.runtime/credential-export.json'
    source.write_text(json.dumps(directory,indent=2),encoding='utf-8');protect(source)
    print(f'{renamed} identities renamed in place; 36 account credentials verified; private CSV source prepared.')

if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('identity_export.failed',component='provisioning',exception=error)
        print('Identity migration/export failed; sanitized diagnostic '+event['event_id']);sys.exit(1)
