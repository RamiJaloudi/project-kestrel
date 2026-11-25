"""Retained compiler output and long-build warnings; no automatic timeout/kill."""
from pathlib import Path
import os
import subprocess
import sys
import threading
import time
import uuid

root=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
sys.stderr.reconfigure(encoding='utf-8',errors='replace')
sys.path.insert(0,str(root/'backend'))
from kestrel.diagnostics import emit,log_path

directory=log_path();directory.mkdir(parents=True,exist_ok=True)
target=directory/('build-'+uuid.uuid4().hex+'.log')
command=['cmd.exe','/d','/c','npm.cmd run build'] if os.name=='nt' else ['npm','run','build']
process=subprocess.Popen(command,cwd=root/'frontend',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                         encoding='utf-8',errors='replace')
capture_errors=[]


def drain():
    try:
        with target.open('a',encoding='utf-8') as output:
            for line in process.stdout:
                output.write(line);output.flush();print(line,end='',flush=True)
    except Exception as error:
        capture_errors.append(type(error).__name__)
        emit('build.capture_failed',component='build',exception=error)


reader=threading.Thread(target=drain,daemon=True);reader.start()
started=time.monotonic();emit('build.started',component='build')
try:
    while process.poll() is None:
        try: process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            emit('build.still_running',component='build',duration_ms=int((time.monotonic()-started)*1000))
            print('Build still running. Compiler output is retained; manual cancellation/recovery only.',flush=True)
except KeyboardInterrupt:
    if os.name=='nt':subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL)
    else:process.terminate()
    emit('build.manually_cancelled',component='build');raise
reader.join(timeout=5)
emit('build.completed' if process.returncode==0 else 'build.failed',component='build',exit_code=process.returncode,
     duration_ms=int((time.monotonic()-started)*1000))
sys.exit(process.returncode if not capture_errors else 1)
