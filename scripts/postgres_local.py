"""Dedicated loopback PostgreSQL cluster; never alter installed Windows services."""
import getpass
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
runtime = root / '.runtime'
data = runtime / 'pgdata'
config = runtime / 'database.json'
runtime.mkdir(exist_ok=True)
binary = shutil.which('psql')
if binary:
    binaries = Path(binary).parent
else:
    candidates = sorted(Path(r'C:\Program Files\PostgreSQL').glob('*/bin/pg_ctl.exe'), reverse=True)
    if not candidates:
        raise SystemExit('PostgreSQL native binaries required; no service was installed or changed.')
    binaries = candidates[0].parent


def run(arguments, check=True):
    with (runtime/'postgres-setup.log').open('a',encoding='utf-8') as output:
        result = subprocess.run([str(a) for a in arguments], stdout=output, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if check and result.returncode:
        # Native messages can include paths; avoid printing connection material.
        raise SystemExit('Local PostgreSQL command failed. Check .runtime/postgres.log and cluster permissions.')
    return result


if sys.argv[1] == 'stop':
    if (data/'PG_VERSION').exists():
        if run([binaries/'pg_ctl.exe','-D',data,'status'],check=False).returncode == 0:
            run([binaries/'pg_ctl.exe','-D',data,'-m','fast','-w','stop'])
    print('Project PostgreSQL stopped; database retained.')
    sys.exit(0)

if config.exists():
    settings = json.loads(config.read_text())
else:
    settings = {'password':secrets.token_urlsafe(32),'port':55432,'user':'kestrel_local'}
    settings['url'] = f"postgresql+psycopg://{settings['user']}:{settings['password']}@127.0.0.1:{settings['port']}/kestrel"
    config.write_text(json.dumps(settings),encoding='utf-8')
    if os.name == 'nt':
        owner = os.environ.get('USERDOMAIN','')+'\\'+getpass.getuser()
        run(['icacls.exe',config,'/inheritance:r','/grant:r',owner+':(F)'])
if not (data/'PG_VERSION').exists():
    password_file = runtime / 'pg-init-password'
    password_file.write_text(settings['password'],encoding='utf-8')
    try:
        run([binaries/'initdb.exe','-D',data,'-U',settings['user'],'--auth=scram-sha-256',
             '--encoding=UTF8','--locale=C','--pwfile',password_file])
    finally:
        password_file.unlink(missing_ok=True)
if run([binaries/'pg_ctl.exe','-D',data,'status'],check=False).returncode != 0:
    with socket.socket() as probe:
        try: probe.bind(('127.0.0.1',settings['port']))
        except OSError: raise SystemExit('Dedicated PostgreSQL port occupied; no other process was stopped.')
    run([binaries/'pg_ctl.exe','-D',data,'-l',runtime/'postgres.log','-o',
         f"-h 127.0.0.1 -p {settings['port']}",'-w','start'])
import psycopg
with psycopg.connect(host='127.0.0.1',port=settings['port'],dbname='postgres',user=settings['user'],
                     password=settings['password'],autocommit=True) as connection:
    if not connection.execute("SELECT 1 FROM pg_database WHERE datname='kestrel'").fetchone():
        connection.execute('CREATE DATABASE kestrel')
print('Project PostgreSQL ready on loopback port 55432; credentials remain in ignored local configuration.')
