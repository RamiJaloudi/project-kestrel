"""One visible console per actual component; safe summaries and retained state."""
import ctypes
import errno
import json
import os
from pathlib import Path
import sys
import threading
import time
import http.client
import uuid

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.diagnostics import emit,configure_console,metrics,activity

TITLES={'https':'Kestrel API - HTTPS portals and Swagger :8443',
    'http':'Kestrel Redirect - HTTP links to HTTPS :8000',
    'postgres':'Kestrel PostgreSQL - database and queue health',
    'monitor':'Kestrel Monitor - service health and manual recovery',
    'worker':'Kestrel Worker - OCR, DDR and document jobs'}

STATUS_WRITE_LOCK=threading.Lock()
STATUS_RETRY_DELAYS=(0.025,0.05,0.1)


def transient_status_error(error):
    # Windows readers/antivirus can briefly deny replacement of an open file.
    return isinstance(error,PermissionError) or getattr(error,'winerror',None) in {5,32,33} or error.errno in {errno.EACCES,errno.EPERM,errno.EBUSY,errno.EAGAIN}


def write_status(directory,component,state,*,stop=None):
    # Final and pulse writers must not share a temporary file or overtake each
    # other. A pulse delayed until after shutdown must not overwrite final state.
    with STATUS_WRITE_LOCK:
        if stop is not None and stop.is_set():return None
        snapshot={'component':component,'pid':os.getpid(),'at':int(time.time()),'supervisor_run':os.environ.get('KESTREL_SUPERVISOR_RUN','standalone'),**metrics(component),**state}
        path=directory/(component+'.json')
        temporary=directory/(component+'.'+str(os.getpid())+'.'+uuid.uuid4().hex+'.tmp')
        for attempt in range(len(STATUS_RETRY_DELAYS)+1):
            try:
                temporary.write_text(json.dumps(snapshot),encoding='utf-8')
                temporary.replace(path)
                return snapshot
            except OSError as error:
                if not transient_status_error(error) or attempt==len(STATUS_RETRY_DELAYS):raise
                time.sleep(STATUS_RETRY_DELAYS[attempt])
        # Failed writes retain their own temporary evidence. They never refresh
        # the last published timestamp, and old retained files are untouched.


def pulse_failure(component,error):
    try:emit('process.pulse_failed',component=component,exception=error)
    except Exception:
        # Diagnostic storage may also be unavailable. Never print exception
        # messages or let that secondary failure kill the heartbeat thread.
        pass


def pulse(directory,component,state,stop,progress):
    while not stop.is_set():
        began=time.monotonic()
        try:
            current=dict(state)
            if component in {'https','http'}:
                try:
                    from local_health import context
                    connection=http.client.HTTPSConnection('localhost',8443,context=context(),timeout=2) if component=='https' else http.client.HTTPConnection('localhost',8000,timeout=2)
                    try:
                        connection.request('GET','/health/ready');response=connection.getresponse()
                        good=response.status==(200 if component=='https' else 308)
                        response.read()
                    finally:connection.close()
                    current['health']='ready' if good else 'unavailable'
                except Exception:current['health']='unavailable'
            if component=='worker' and time.monotonic()-progress['at']>100:current['health']='unresponsive'
            snapshot=write_status(directory,component,current,stop=stop)
            if snapshot is None:return
            print(f"[{time.strftime('%H:%M:%S')}] PULSE uptime={snapshot['uptime_s']}s health={snapshot['health']} completed={snapshot['completed']} failed={snapshot['failed']} last={snapshot['last_activity']} {snapshot['details']}",flush=True)
            emit('process.pulse',component=component,status=snapshot['health'],uptime_s=snapshot['uptime_s'],completed=snapshot['completed'],failed=snapshot['failed'])
        except Exception as error:pulse_failure(component,error)
        stop.wait(max(0,10-(time.monotonic()-began)))


def stop_pulse(directory,component,state,stop,thread):
    stop.set()
    thread.join(timeout=3)
    # write_status also serializes with an in-flight pulse and checks its stop
    # event under the same lock. A late probe cannot republish ready afterwards.
    write_status(directory,component,state)


def run(component):
    if component not in TITLES:raise ValueError('Unknown local component')
    os.environ['KESTREL_COMPONENT']=component
    directory=root/'.runtime/status';directory.mkdir(exist_ok=True,parents=True)
    stop=threading.Event()
    state={'health':'starting','details':''}
    progress={'at':time.monotonic()}
    # Retain the first safe startup record before importing SQL/ORM/worker stacks.
    write_status(directory,component,state)
    emit('process.bootstrap',component=component)
    if os.name=='nt':
        try:
            sys.stdout=open('CONOUT$','w',encoding='utf-8',buffering=1);sys.stderr=sys.stdout
            ctypes.windll.kernel32.SetConsoleTitleW(TITLES[component])
        except OSError as error:emit('console.attach_unavailable',component=component,exception=error)
    configure_console()
    print(TITLES[component],flush=True)
    print('Pulse every 10s | retained diagnostics: .runtime/logs | manual process restart',flush=True)
    pulse_thread=threading.Thread(target=pulse,args=(directory,component,state,stop,progress),daemon=True)
    pulse_thread.start()
    emit('process.starting',component=component)
    try:
        from kestrel.database import make_engine,database_url,factory
        from sqlalchemy import text,select,func
        from kestrel.models import AnalysisJob
        if component in {'https','http'}:
            import uvicorn
            options={'host':'127.0.0.1','port':8443 if component=='https' else 8000,'proxy_headers':False,'access_log':False,'log_config':None}
            if component=='https':options.update(ssl_keyfile=str(root/'.runtime/local.key'),ssl_certfile=str(root/'.runtime/local.pem'))
            state['health']='running'
            uvicorn.run('kestrel.main:app' if component=='https' else 'kestrel.redirect:app',**options)
        elif component=='worker':
            from kestrel.services.jobs import run_once
            from kestrel.services.ocr_jobs import run_once as run_ocr
            from kestrel.services.ddr_execution import run_once as run_ddr
            engine=make_engine(database_url())
            if engine.dialect.name!='postgresql':raise RuntimeError('Local worker requires PostgreSQL')
            from kestrel.services.sla_alerts import scan_due
            sessions=factory(engine);state['health']='ready';next_sla_scan=0.0
            while True:
                with engine.connect() as connection:connection.execute(text('SELECT 1'))
                progress['at']=time.monotonic()
                if time.monotonic()>=next_sla_scan:
                    alerts=scan_due(sessions)
                    activity(component,'sla.scan')
                    if alerts:print(f'SLA scan: created {alerts} scoped operational alert(s)',flush=True)
                    next_sla_scan=time.monotonic()+30
                    progress['at']=time.monotonic()
                if not run_ocr(sessions,heartbeat=lambda:progress.update(at=time.monotonic())) and not run_ddr(sessions,heartbeat=lambda:progress.update(at=time.monotonic())) and not run_once(sessions,heartbeat=lambda:progress.update(at=time.monotonic())):time.sleep(1)
        elif component=='postgres':
            from sqlalchemy.engine import make_url
            url=make_url(database_url())
            if url.get_backend_name()!='postgresql':raise RuntimeError('Local database monitor requires PostgreSQL')
            url=url.update_query_dict({'connect_timeout':'3','options':'-c statement_timeout=3000'})
            engine=make_engine(url.render_as_string(hide_password=False));previous=None
            while True:
                try:
                    with engine.connect() as connection:
                        counts=dict(connection.execute(select(AnalysisJob.state,func.count()).group_by(AnalysisJob.state)).all())
                    state.update(health='ready',details='queue='+json.dumps(counts,sort_keys=True))
                    activity(component,'database.probe')
                except Exception as error:
                    state.update(health='unavailable',details='database probe failed')
                    emit('database.probe_failed',component=component,exception=error)
                    activity(component,'database.probe_failed',failed=True)
                if previous!=state['health']:print('Database '+state['health'],flush=True);previous=state['health']
                time.sleep(10)
        else:
            from local_health import healthy
            previous=None
            while True:
                ok=healthy();worker_ok=False;postgres_ok=False
                try:
                    row=json.loads((directory/'worker.json').read_text())
                    worker_ok=row['health']=='ready' and int(time.time())-row['at']<25 and row.get('supervisor_run')==os.environ.get('KESTREL_SUPERVISOR_RUN','standalone')
                    row=json.loads((directory/'postgres.json').read_text())
                    postgres_ok=row['health']=='ready' and int(time.time())-row['at']<25 and row.get('supervisor_run')==os.environ.get('KESTREL_SUPERVISOR_RUN','standalone')
                except (OSError,ValueError,KeyError):pass
                state.update(health='ready' if ok and worker_ok and postgres_ok else 'degraded',details=f'HTTPS+redirect={"ready" if ok else "unavailable"} worker={"ready" if worker_ok else "unavailable"} postgres={"ready" if postgres_ok else "unavailable"}')
                activity(component,'services.probe',failed=not(ok and worker_ok and postgres_ok))
                if state['health']!=previous:
                    emit('services.'+state['health'],component=component);print(state['details'],flush=True);previous=state['health']
                time.sleep(10)
        state['health']='stopped';emit('process.stopped',component=component)
    except BaseException as error:
        state['health']='failed'
        row=emit('process.failed',component=component,exception=error)
        print('Component failed; manual restart required. Diagnostic='+row['event_id'],flush=True)
        raise SystemExit(1)
    finally:
        stop_pulse(directory,component,state,stop,pulse_thread)

if __name__=='__main__':run(sys.argv[1])
