"""Create requested private demo credentials once; never print their values."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import quote

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env
from kestrel.demo_names import NAMED

path=Path(os.environ.get('KESTREL_ENV_FILE',root/'.env'))
values=read_env(path)
settings=json.loads((root/'.runtime/database.json').read_text())
defaults={
 'KESTREL_ENV':'LOCAL','KESTREL_DB_HOST':'127.0.0.1','KESTREL_DB_PORT':str(settings['port']),
 'KESTREL_DB_NAME':'kestrel','KESTREL_DB_USER':settings['user'],'KESTREL_DB_PASSWORD':settings['password'],
 'KESTREL_DATABASE_URL':settings['url'],
 **NAMED,
 'KESTREL_INTERVIEW_PASSWORD':secrets.token_urlsafe(24),
 'KESTREL_PROVISION_INTERVIEW_ACCOUNTS':'true'}
defaults.update(KESTREL_DUMMY_PASSWORD=values.get('KESTREL_INTERVIEW_PASSWORD',defaults['KESTREL_INTERVIEW_PASSWORD']),
                KESTREL_PROVISION_DUMMY_ACCOUNTS='true',KESTREL_SEED_DOCUMENT_DEMO='true',KESTREL_OPENAI_ENABLED='false')
changed=False
for key,value in defaults.items():
    if key not in values:values[key]=value;changed=True
if changed:
    path.write_text('# Private synthetic demo credentials. Never commit or publish.\n'+
        '\n'.join(key+'='+json.dumps(value) for key,value in values.items())+'\n',encoding='utf-8')
if os.name=='nt':
    owner=os.environ['USERDOMAIN']+'\\'+os.environ['USERNAME']
    result=subprocess.run(['icacls.exe',str(path),'/inheritance:r','/grant:r',owner+':(F)'],capture_output=True)
    if result.returncode:raise SystemExit('Could not restrict local .env permissions')
print('Private .env ready; credential values were not printed.')
