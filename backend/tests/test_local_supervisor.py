"""Pure process/heartbeat supervision tests; no live service or DB changes."""
import importlib.util
import errno
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[2]


def module(name):
    spec=importlib.util.spec_from_file_location('test_'+name,ROOT/'scripts'/(name+'.py'));value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def process(pid=123,code=None):return SimpleNamespace(pid=pid,poll=lambda:code)


def test_launch_tracks_unbuffered_python_not_a_persistent_cmd_shell():
    supervisor=module('serve_local');command=supervisor.launch_command('postgres')
    assert command[0]==supervisor.sys.executable and command[1]=='-u' and command[-1]=='postgres'
    assert Path(command[2]).name=='console_runner.py'
    assert not any(value.lower() in {'cmd.exe','/k','/c'} for value in command)


def test_python_failure_is_detected_even_when_shell_and_other_component_survive():
    supervisor=module('serve_local');idle_shell=process(999);python=process(123,1);other=process(456)
    assert idle_shell.poll() is None and other.poll() is None
    assert supervisor.component_failure({'postgres':python,'worker':other},{},'new',2,started=0,ready=False)==('postgres','child_exit',1)


def test_failed_status_is_detected_while_failed_console_process_is_still_alive():
    supervisor=module('serve_local')
    status={'postgres':{'supervisor_run':'new','at':1,'health':'failed'}}
    assert supervisor.component_failure({'postgres':process()},status,'new',2,started=0,ready=False)==('postgres','component_failed',None)


def test_old_ready_heartbeat_cannot_satisfy_startup_and_runtime_loss_fails_closed():
    supervisor=module('serve_local');children={'postgres':process()};old={'postgres':{'supervisor_run':'old','at':50,'health':'ready'}}
    assert supervisor.component_failure(children,old,'new',46,started=0,ready=False)==('supervisor','startup_timeout',None)
    assert supervisor.component_failure(children,old,'new',50,started=0,ready=True)==('postgres','heartbeat_identity',None)
    stale={'postgres':{'supervisor_run':'new','at':1,'health':'ready'}}
    assert supervisor.component_failure(children,stale,'new',50,started=0,ready=True)==('postgres','heartbeat_stale',None)


def test_transient_file_read_failure_keeps_last_observation_but_never_extends_freshness(tmp_path,monkeypatch):
    supervisor=module('serve_local');record={'supervisor_run':'new','at':100,'health':'ready'}
    previous={'http':record};children={'http':process()}
    original=Path.read_text
    def locked(path,*args,**kwargs):
        if path.name=='http.json':raise PermissionError('Synthetic atomic replacement conflict')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',locked)
    observed=supervisor.current_status(tmp_path,previous)
    assert observed['http']==record and observed['http']['at']==100
    assert supervisor.component_failure(children,observed,'new',110,started=0,ready=True) is None
    assert supervisor.component_failure(children,observed,'new',126,started=0,ready=True)==('http','heartbeat_stale',None)


def test_supervisor_evidence_excludes_unknown_fields_and_exception_contents(tmp_path,monkeypatch,capsys):
    supervisor=module('serve_local');monkeypatch.setattr(supervisor,'root',tmp_path);directory=tmp_path/'.runtime/status';directory.mkdir(parents=True)
    supervisor.record(directory,'synthetic-run','failed',{'postgres':process()},event='child_exit',failed_component='postgres',exit_code=1,exception_type='ImportError',secret='SYNTHETIC_SECRET_CANARY')
    captured=capsys.readouterr();data=(directory/'supervisor.json').read_text()
    assert 'SYNTHETIC_SECRET_CANARY' not in data+captured.out+captured.err and 'child_exit' in captured.err
    assert json.loads(data)['children']=={'postgres':123}


def test_health_uses_read_only_process_liveness_check():
    health=module('local_health');assert health.process_alive(os.getpid())
    assert not health.process_alive(-1) and not health.process_alive(999999995)


def test_readiness_rejects_previous_run_and_dead_python_even_if_http_is_ready(tmp_path,monkeypatch):
    health=module('local_health');monkeypatch.setattr(health,'__file__',str(tmp_path/'scripts/local_health.py'))
    directory=tmp_path/'.runtime/status';directory.mkdir(parents=True)
    monkeypatch.setattr(health,'context',lambda:None)
    response=SimpleNamespace(status=200,url='https://localhost:8443/health/ready')
    class Response:
        def __enter__(self):return response
        def __exit__(self,*args):pass
    monkeypatch.setattr(health.urllib.request,'build_opener',lambda *args:SimpleNamespace(open=lambda *args,**kwargs:Response()))
    monkeypatch.setattr(health,'process_alive',lambda pid:pid!=42)
    (directory/'supervisor.json').write_text(json.dumps({'health':'ready','pid':1,'run_id':'new'}))
    now=int(health.time.time())
    for component in ['https','http','worker','postgres','monitor']:(directory/(component+'.json')).write_text(json.dumps({'health':'ready','pid':1,'at':now,'supervisor_run':'new'}))
    assert health.healthy(check_components=True)
    postgres=directory/'postgres.json';postgres.write_text(json.dumps({'health':'ready','pid':1,'at':now,'supervisor_run':'old'}))
    assert not health.healthy(check_components=True)
    postgres.write_text(json.dumps({'health':'ready','pid':42,'at':now,'supervisor_run':'new'}))
    assert not health.healthy(check_components=True)


@pytest.mark.parametrize('operation',['write_text','replace'])
def test_status_publication_retries_transient_writer_failure_then_succeeds(tmp_path,monkeypatch,operation):
    runner=module('console_runner');original=getattr(Path,operation);attempts=[];delays=[]
    old=tmp_path/'https.54496.tmp';old.write_text('retained prior failure evidence')
    def transient(path,*args,**kwargs):
        if path.parent==tmp_path and path.name.startswith('https.') and path.name!=old.name:
            attempts.append(path.name)
            if len(attempts)==1:raise PermissionError('Synthetic sharing violation')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,operation,transient)
    monkeypatch.setattr(runner.time,'sleep',delays.append)
    result=runner.write_status(tmp_path,'https',{'health':'ready','details':''})
    assert len(attempts)==2 and delays==[runner.STATUS_RETRY_DELAYS[0]]
    assert json.loads((tmp_path/'https.json').read_text())==result
    assert old.read_text()=='retained prior failure evidence'


def test_status_publication_exhaustion_keeps_last_timestamp_and_stale_detection(tmp_path,monkeypatch):
    runner=module('console_runner');supervisor=module('serve_local');path=tmp_path/'https.json'
    previous={'supervisor_run':'new','at':100,'health':'ready'};path.write_text(json.dumps(previous));before=path.read_bytes()
    attempts=[];delays=[]
    def denied(*args,**kwargs):
        attempts.append(1);raise PermissionError('Synthetic persistent sharing violation')
    monkeypatch.setattr(Path,'replace',denied);monkeypatch.setattr(runner.time,'sleep',delays.append)
    monkeypatch.setattr(runner.time,'time',lambda:200)
    with pytest.raises(PermissionError):runner.write_status(tmp_path,'https',{'health':'ready','details':''})
    assert len(attempts)==len(runner.STATUS_RETRY_DELAYS)+1 and delays==list(runner.STATUS_RETRY_DELAYS)
    assert path.read_bytes()==before and json.loads(path.read_text())['at']==100
    assert supervisor.component_failure({'https':process()},{'https':previous},'new',126,started=0,ready=True)==('https','heartbeat_stale',None)


def test_status_publication_does_not_retry_permanent_storage_failure(tmp_path,monkeypatch):
    runner=module('console_runner');attempts=[];delays=[]
    def full(*args,**kwargs):
        attempts.append(1);raise OSError(errno.ENOSPC,'Synthetic disk full')
    monkeypatch.setattr(Path,'replace',full);monkeypatch.setattr(runner.time,'sleep',delays.append)
    with pytest.raises(OSError):runner.write_status(tmp_path,'postgres',{'health':'ready','details':''})
    assert len(attempts)==1 and delays==[] and not (tmp_path/'postgres.json').exists()


def test_pulse_survives_failed_publication_and_retains_only_sanitized_diagnostic(tmp_path,monkeypatch,capsys):
    runner=module('console_runner');original=Path.replace;attempts=[];observed=[]
    directory=tmp_path/'status';directory.mkdir();path=directory/'postgres.json'
    path.write_text(json.dumps({'at':100,'health':'ready'}))
    monkeypatch.setenv('KESTREL_LOG_DIR',str(tmp_path/'logs'))
    monkeypatch.setattr(runner.time,'time',lambda:200);monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    def first_cycle_denied(source,*args,**kwargs):
        attempts.append(1)
        if len(attempts)<=len(runner.STATUS_RETRY_DELAYS)+1:raise PermissionError('SYNTHETIC_SECRET_EXCEPTION_CANARY')
        return original(source,*args,**kwargs)
    monkeypatch.setattr(Path,'replace',first_cycle_denied)
    class Stop:
        cycles=0
        def is_set(self):return self.cycles==2
        def wait(self,timeout):
            observed.append(json.loads(path.read_text())['at']);self.cycles+=1
    runner.pulse(directory,'postgres',{'health':'ready','details':''},Stop(),{'at':0})
    records=[json.loads(line) for line in (tmp_path/'logs'/'postgres.jsonl').read_text().splitlines()]
    failed=[r for r in records if r['event']=='process.pulse_failed']
    assert observed==[100,200] and len(failed)==1 and failed[0]['exception_type']=='PermissionError'
    assert [r['event'] for r in records]==['process.pulse_failed','process.pulse']
    captured=capsys.readouterr()
    assert 'SYNTHETIC_SECRET_EXCEPTION_CANARY' not in json.dumps(records)+captured.out+captured.err


def test_diagnostic_storage_failure_does_not_kill_subsequent_pulses(tmp_path,monkeypatch,capsys):
    runner=module('console_runner');writes=[];original=runner.write_status
    def publish(*args,**kwargs):writes.append(1);return original(*args,**kwargs)
    def unavailable(*args,**kwargs):raise OSError('SYNTHETIC_LOG_SECRET_CANARY')
    monkeypatch.setattr(runner,'write_status',publish);monkeypatch.setattr(runner,'emit',unavailable)
    class Stop:
        cycles=0
        def is_set(self):return self.cycles==2
        def wait(self,timeout):self.cycles+=1
    runner.pulse(tmp_path,'postgres',{'health':'ready','details':''},Stop(),{'at':0})
    captured=capsys.readouterr()
    assert len(writes)==2 and json.loads((tmp_path/'postgres.json').read_text())['health']=='ready'
    assert 'SYNTHETIC_LOG_SECRET_CANARY' not in captured.out+captured.err


def test_terminal_status_waits_for_active_pulse_and_uses_a_distinct_temporary_file(tmp_path,monkeypatch):
    runner=module('console_runner');original=Path.write_text;entered=threading.Event();release=threading.Event();stop=threading.Event()
    names=[];states=[];errors=[]
    def gated(path,value,*args,**kwargs):
        if path.parent==tmp_path and path.suffix=='.tmp':
            names.append(path.name);states.append(json.loads(value)['health'])
            if len(names)==1:
                entered.set()
                if not release.wait(3):raise TimeoutError('Synthetic test barrier timed out')
        return original(path,value,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',gated)
    def capture(operation):
        try:operation()
        except Exception as error:errors.append(type(error).__name__)
    active=threading.Thread(target=lambda:capture(lambda:runner.write_status(tmp_path,'https',{'health':'ready','details':''},stop=stop)))
    final=threading.Thread(target=lambda:capture(lambda:runner.stop_pulse(tmp_path,'https',{'health':'stopped','details':''},stop,active)))
    active.start()
    try:
        assert entered.wait(1)
        final.start();assert stop.wait(1)
        assert names and states==['ready']
    finally:
        release.set();active.join(4)
        if final.ident is not None:final.join(4)
    assert not active.is_alive() and not final.is_alive() and errors==[]
    assert states==['ready','stopped'] and len(set(names))==2
    assert json.loads((tmp_path/'https.json').read_text())['health']=='stopped'


def test_delayed_pulse_cannot_overwrite_terminal_status_after_stop(tmp_path):
    runner=module('console_runner');stop=threading.Event();stop.set()
    final=runner.write_status(tmp_path,'https',{'health':'stopped','details':''})
    before=(tmp_path/'https.json').read_bytes()
    assert runner.write_status(tmp_path,'https',{'health':'ready','details':''},stop=stop) is None
    assert (tmp_path/'https.json').read_bytes()==before
    assert final['health']=='stopped' and list(tmp_path.glob('*.tmp'))==[]


def test_late_health_probe_cannot_change_shared_terminal_health(tmp_path,monkeypatch):
    runner=module('console_runner');entered=threading.Event();release=threading.Event();stop=threading.Event();errors=[]
    state={'health':'running','details':''}
    monkeypatch.setitem(runner.sys.modules,'local_health',SimpleNamespace(context=lambda:None))
    class Connection:
        def __init__(self,*args,**kwargs):pass
        def request(self,*args,**kwargs):pass
        def getresponse(self):
            entered.set()
            if not release.wait(3):raise TimeoutError('Synthetic probe barrier timed out')
            return SimpleNamespace(status=200,read=lambda:b'')
        def close(self):pass
    monkeypatch.setattr(runner.http.client,'HTTPSConnection',Connection)
    def capture(operation):
        try:operation()
        except Exception as error:errors.append(type(error).__name__)
    active=threading.Thread(target=lambda:capture(lambda:runner.pulse(tmp_path,'https',state,stop,{'at':0})))
    final=threading.Thread(target=lambda:capture(lambda:runner.stop_pulse(tmp_path,'https',state,stop,active)))
    active.start()
    try:
        assert entered.wait(1)
        state['health']='failed';final.start();assert stop.wait(1)
    finally:
        release.set();active.join(4)
        if final.ident is not None:final.join(4)
    assert not active.is_alive() and not final.is_alive() and errors==[]
    assert state['health']=='failed' and json.loads((tmp_path/'https.json').read_text())['health']=='failed'
