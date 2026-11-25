"""Supervise actual project Python processes, never persistent shell liveness."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

root=Path(__file__).resolve().parents[1]
COMPONENTS=('https','http','postgres','worker','monitor')


def launch_command(component):
    if component not in COMPONENTS:raise ValueError('Unknown local component')
    return [sys.executable,'-u',str(root/'scripts/console_runner.py'),component]


def component_failure(children,status,run_id,now,*,started,ready):
    """An idle shell or another surviving component cannot mask Python failure."""
    for component,child in children.items():
        code=child.poll()
        if code is not None:return component,'child_exit',code
        row=status.get(component,{})
        if row.get('supervisor_run')!=run_id:
            if ready:return component,'heartbeat_identity',None
            continue
        if row.get('health') in {'failed','stopped','unresponsive'}:return component,'component_failed',None
        if ready and now-row.get('at',0)>25:return component,'heartbeat_stale',None
    if now-started>45 and not ready:return 'supervisor','startup_timeout',None
    return None


def current_status(directory,previous=None):
    # Windows can briefly refuse a read while an atomic replacement is in
    # progress. Keep the last observed record without refreshing its timestamp;
    # the ordinary 25-second stale check still closes a genuinely lost pulse.
    result=dict(previous or {})
    for component in COMPONENTS:
        try:result[component]=json.loads((directory/(component+'.json')).read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    return result


def record(directory,run_id,health,children,**fields):
    # No command lines, environment, credentials, source or exception messages.
    row={'component':'supervisor','pid':os.getpid(),'run_id':run_id,'at':int(time.time()),'health':health,
        'children':{key:child.pid for key,child in children.items()},**{k:v for k,v in fields.items() if k in {'event','failed_component','exit_code','exception_type'}}}
    temporary=directory/('supervisor.'+str(os.getpid())+'.tmp');temporary.write_text(json.dumps(row),encoding='utf-8');temporary.replace(directory/'supervisor.json')
    logs=root/'.runtime/logs';logs.mkdir(parents=True,exist_ok=True)
    with (logs/'supervisor-events.jsonl').open('a',encoding='utf-8') as output:output.write(json.dumps(row)+'\n')
    print(json.dumps(row),file=sys.stderr if health=='failed' else sys.stdout,flush=True)


def stop_children(children):
    for child in children.values():
        if child.poll() is not None:continue
        if os.name=='nt':
            # Only handles created by this supervisor enter this owned-tree stop.
            subprocess.run(['taskkill.exe','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        else:child.terminate()
    for child in children.values():
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)


def main():
    children={};run_id=uuid.uuid4().hex;directory=root/'.runtime/status';directory.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'KESTREL_SUPERVISOR_RUN':run_id,'PYTHONUNBUFFERED':'1'};ready=False;started=time.time();failed=False
    record(directory,run_id,'starting',children,event='supervisor.starting')
    try:
        for component in COMPONENTS:
            options={'cwd':str(root),'env':env}
            if os.name=='nt':
                visible=subprocess.STARTUPINFO();visible.dwFlags|=subprocess.STARTF_USESHOWWINDOW;visible.wShowWindow=1
                options.update(creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=visible)
            children[component]=subprocess.Popen(launch_command(component),**options)
            record(directory,run_id,'starting',children,event='component.launched')
        status={}
        while True:
            status=current_status(directory,status);now=time.time()
            failure=component_failure(children,status,run_id,now,started=started,ready=ready)
            if failure:
                failed=True;component,event,code=failure
                record(directory,run_id,'failed',children,event=event,failed_component=component,exit_code=code)
                return 1
            all_ready=all(status.get(component,{}).get('health')=='ready' and status[component].get('supervisor_run')==run_id and now-status[component].get('at',0)<25 for component in COMPONENTS)
            if all_ready and not ready:
                ready=True;record(directory,run_id,'ready',children,event='supervisor.ready')
            time.sleep(0.2)
    except BaseException as error:
        failed=True;record(directory,run_id,'failed',children,event='supervisor.failed',exception_type=type(error).__name__)
        return 1
    finally:
        stop_children(children)
        if not failed:record(directory,run_id,'stopped',children,event='supervisor.stopped')


if __name__=='__main__':raise SystemExit(main())
