"""Append-only local diagnostics: no exception messages, locals or request bodies."""
import json
import logging
import os
from pathlib import Path
import threading
import time
import traceback
import uuid

LOCK=threading.Lock()
METRICS={}
STARTED=time.monotonic()


def activity(component,event,*,failed=False,method=None,status=None,route=None,duration_ms=None,correlation_id=None):
    # Caller supplies only framework route templates, never actual URLs/queries.
    with LOCK:
        row=METRICS.setdefault(component,{'completed':0,'failed':0,'last_activity':'none'})
        row['completed']+=int(event!='job.started')
        row['failed']+=int(failed)
        row['last_activity']=time.strftime('%H:%M:%S',time.gmtime())+' '+event
    summary=f'{method} {route} -> {status} {duration_ms}ms' if method else event
    emit(event,component=component,method=method,status=status,duration_ms=duration_ms,route=route,correlation_id=correlation_id)
    print(f'[{time.strftime("%H:%M:%S")}] {component} {summary}',flush=True)


def metrics(component):
    with LOCK:return {'uptime_s':int(time.monotonic()-STARTED),**METRICS.get(component,{'completed':0,'failed':0,'last_activity':'none'})}


def log_path():
    return Path(os.environ.get('KESTREL_LOG_DIR',str(Path(__file__).resolve().parents[2]/'.runtime'/'logs')))


def emit(event, *, correlation_id=None, component='api', exception=None, **safe_fields):
    fields={k:v for k,v in safe_fields.items() if k in {'status','duration_ms','port','exit_code','failures','method','route','uptime_s','completed','failed'}}
    row={'event_id':str(uuid.uuid4()),'occurred_at':int(time.time()),'category':'technical',
         'component':component,'event':event,'correlation_id':correlation_id,**fields}
    if exception is not None:
        row['exception_type']=type(exception).__name__
        row['frames']=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno}
                       for f in traceback.extract_tb(exception.__traceback__)]
    directory=log_path();directory.mkdir(parents=True,exist_ok=True)
    with LOCK, (directory/(component+'.jsonl')).open('a',encoding='utf-8') as output:
        output.write(json.dumps(row,ensure_ascii=True)+'\n')
        output.flush()
    return row


class SafeConsoleHandler(logging.Handler):
    def emit(self, record):
        exception=record.exc_info[1] if record.exc_info else None
        # Do not interpolate framework message/arguments; SQL/provider errors may contain data.
        row=emit('runtime.'+record.levelname.lower(),component=os.environ.get('KESTREL_COMPONENT','backend'),exception=exception)
        known={'Started server process [%d]':'API process started',
            'Waiting for application startup.':'Waiting for application startup',
            'Application startup complete.':'Application startup complete',
            'Uvicorn running on %s://%s:%d (Press CTRL+C to quit)':'Listener accepting connections',
            'Shutting down':'Shutting down','Waiting for application shutdown.':'Waiting for shutdown',
            'Application shutdown complete.':'Shutdown complete','Finished server process [%d]':'Process stopped'}
        summary=known.get(record.msg,'Runtime '+record.levelname.lower()+'; inspect sanitized diagnostic') if isinstance(record.msg,str) else 'Runtime event'
        print(f"[{record.levelname}] {summary}; event={row['event_id']}" +
              (f" ({row['exception_type']})" if exception else ''),flush=True)


def configure_console():
    root=logging.getLogger()
    root.handlers=[SafeConsoleHandler()]
    root.setLevel(logging.INFO)
    for name in ['uvicorn','uvicorn.error','uvicorn.access','sqlalchemy']:
        logger=logging.getLogger(name);logger.handlers=[];logger.propagate=True
