"""Add only the project pgAdmin connection, using a protected libpq passfile."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import load_env
load_env()
runtime=root/'.runtime';passfile=runtime/'pgadmin-passfile.conf';serverfile=runtime/'pgadmin-servers.json'
keys=['KESTREL_DB_HOST','KESTREL_DB_PORT','KESTREL_DB_NAME','KESTREL_DB_USER','KESTREL_DB_PASSWORD']
values=[os.environ[k] for k in keys]
if values[0] not in {'127.0.0.1','localhost'}:raise SystemExit('Automatic pgAdmin setup is limited to the local demo.')
escape=lambda s:s.replace('\\','\\\\').replace(':','\\:')
passfile.write_text(':'.join(map(escape,values))+'\n',encoding='utf-8')
if os.name=='nt':
    owner=os.environ['USERDOMAIN']+'\\'+os.environ['USERNAME']
    completed=subprocess.run(['icacls.exe',str(passfile),'/inheritance:r','/grant:r',owner+':(F)'],capture_output=True)
    if completed.returncode:raise SystemExit('Could not protect pgAdmin password file')
name='Kestrel interview demo (.env credentials)'
definition={'Name':name,'Group':'Project Kestrel','Host':values[0],'Port':int(values[1]),'Username':values[3],
            'MaintenanceDB':values[2],'SSLMode':'prefer','ConnectionParameters':{'sslmode':'prefer','passfile':str(passfile)}}
serverfile.write_text(json.dumps({'Servers':{'1':definition}}),encoding='utf-8')
config=Path(os.environ['APPDATA'])/'pgAdmin'/'pgadmin4.db'
if config.exists():
    with sqlite3.connect(f'file:{config.as_posix()}?mode=ro',uri=True) as db:
        if db.execute('SELECT 1 FROM server WHERE name=?',(name,)).fetchone():
            print('Project pgAdmin connection already registered; passfile refreshed.');sys.exit(0)
candidates=sorted(Path(r'C:\Program Files\PostgreSQL').glob('*/pgAdmin 4/web/setup.py'),reverse=True)
if not candidates:raise SystemExit('pgAdmin setup script not found; psql remains available.')
setup=candidates[0];python=setup.parents[1]/'python/python.exe'
with (runtime/'pgadmin-setup.log').open('a',encoding='utf-8') as log:
    result=subprocess.run([str(python),str(setup),'load-servers',str(serverfile),'--sqlite-path',str(config)],stdout=log,stderr=subprocess.STDOUT)
if result.returncode:raise SystemExit('pgAdmin connection import failed; see private setup log.')
print('Project pgAdmin connection registered; other connections preserved. No password printed.')
