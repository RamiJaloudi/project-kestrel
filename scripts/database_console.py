"""Launch psql for the dedicated project DB without exposing its password in argv."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
settings=json.loads((root/'.runtime/database.json').read_text())
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import load_env
load_env()
settings.update(password=os.environ.get('KESTREL_DB_PASSWORD',settings['password']),
                port=int(os.environ.get('KESTREL_DB_PORT',settings['port'])),
                user=os.environ.get('KESTREL_DB_USER',settings['user']))
binary=shutil.which('psql')
if not binary:
    binaries=sorted(Path(r'C:\Program Files\PostgreSQL').glob('*/bin/psql.exe'),reverse=True)
    if not binaries:raise SystemExit('psql is not installed.')
    binary=str(binaries[0])
environment=os.environ.copy()
environment['PGPASSWORD']=settings['password']
environment['PGAPPNAME']='Kestrel local operator console'
environment['PGCLIENTENCODING']='UTF8'
print('Kestrel project SQL console: 127.0.0.1:'+str(settings['port'])+' / kestrel')
print('This is an operator console. Changes affect the local demo database. Type \\q to exit.')
subprocess.run([binary,'-h','127.0.0.1','-p',str(settings['port']),'-U',settings['user'],'-d','kestrel'],env=environment)
