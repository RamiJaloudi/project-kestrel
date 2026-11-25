"""Only temporary synthetic owner manifests; no real approval or public binding."""
import concurrent.futures
import json
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import Request,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth_policy import env,PASSWORD
from kestrel.main import create_app
from kestrel import deployment_settings as settings
from kestrel.services import auth
from kestrel.public_boundary import BoundedLimiter
from kestrel.models import LoginThrottle

CHECKS=['backend_full','public_boundary','postgres_restore','frontend_build','tls_proxy','windows_services','backup_recovery','owner_review']


def fixture_owner_files(tmp_path,monkeypatch):
    release=tmp_path/'release';(release/'frontend/dist').mkdir(parents=True);(release/'frontend/dist/index.html').write_text('synthetic fixture build')
    (release/'backend/tests').mkdir(parents=True);(release/'backend/tests/test_fixture.py').write_text('# Temporary synthetic acceptance fixture only')
    private=tmp_path/'owner';private.mkdir();token=private/'proxy.token';token.write_text('SYNTHETIC_PROXY_TOKEN_'+('x'*43))
    config={'schema':'kestrel-public-config-1','mode':'PUBLIC_DEMO','hosts':settings.PUBLIC_HOSTS,'backend_host':'127.0.0.1','backend_port':8000,'workers':1,
        'owner_sid':'S-1-5-21-100','service_sid':'S-1-5-21-101','proxy_sid':'S-1-5-21-102',
        'proxy_token_file':str(token),'approval_file':str(private/'approval.json'),'receipt_file':str(private/'receipt.json')}
    path=private/'config.json';path.write_text(settings.canonical(config),encoding='utf-8')
    monkeypatch.setattr(settings,'ROOT',release)
    monkeypatch.setattr(settings,'_windows_private_file',lambda path,*args:None)  # Only OS identity/ACL boundary is synthetic.
    fingerprint=settings.release_hash();tests=settings.test_suite_hash();configuration=settings.sha(settings.canonical(config));now=int(time.time())
    receipt={'schema':'kestrel-public-acceptance-1','release_hash':fingerprint,'test_suite_hash':tests,'config_hash':configuration,'all_required_passed':True,'required_checks':CHECKS}
    Path(config['receipt_file']).write_text(settings.canonical(receipt),encoding='utf-8')
    approval={'schema':'kestrel-public-approval-1','decision':'approve-public-synthetic-demo','owner_sid':config['owner_sid'],'mode':'PUBLIC_DEMO','hosts':settings.PUBLIC_HOSTS,
        'config_hash':configuration,'release_hash':fingerprint,'test_suite_hash':tests,'receipt_hash':settings.sha(Path(config['receipt_file']).read_bytes()),'approved_at':now,'expires_at':now+600}
    Path(config['approval_file']).write_text(settings.canonical(approval),encoding='utf-8')
    monkeypatch.setenv('KESTREL_ENV','PUBLIC_DEMO');monkeypatch.setenv('KESTREL_PUBLIC_CONFIG',str(path))
    return config,approval,token.read_text()


@pytest.fixture
def public_env(env,tmp_path,monkeypatch):
    config,approval,token=fixture_owner_files(tmp_path,monkeypatch)
    app=create_app(engine=env[1].kw['bind'])
    @app.get('/boundary-fixture',include_in_schema=False)
    def boundary(request:Request):return {'host':request.url.hostname,'scheme':request.url.scheme,'peer':request.client.host,'headers':list(request.headers)}
    @app.post('/body-fixture',include_in_schema=False)
    async def body(request:Request):return {'size':len(await request.body())}
    return env,app,config,token


def proxy_headers(token,**changes):return {'x-kestrel-proxy-token':token,'x-kestrel-proto':'https','x-kestrel-client-ip':'203.0.113.20',**changes}
def client(app,token,host='firm.portal.ramijaloudi.com',peer='127.0.0.1'):
    return TestClient(app,base_url='https://'+host,client=(peer,35000),headers=proxy_headers(token))
def login(http,name):return http.post('/api/v1/auth/login',headers={'origin':str(http.base_url).rstrip('/')},json={'username':name,'password':PASSWORD})


def test_public_startup_requires_exact_current_external_owner_approval(tmp_path,monkeypatch):
    config,approval,_=fixture_owner_files(tmp_path,monkeypatch);assert settings.load_deployment().public
    for key,value in [('decision','not-approved'),('config_hash','a'*64),('release_hash','b'*64),('receipt_hash','c'*64),('expires_at',int(time.time())-1),('hosts',{})]:
        changed={**approval,key:value};Path(config['approval_file']).write_text(settings.canonical(changed))
        with pytest.raises(RuntimeError):settings.load_deployment()
    Path(config['approval_file']).unlink()
    with pytest.raises((RuntimeError,OSError)):settings.load_deployment()


def test_no_public_mode_with_missing_files_unknown_mode_or_bypassed_acl(tmp_path,monkeypatch):
    monkeypatch.setenv('KESTREL_ENV','PUBLIC_DEMO');monkeypatch.delenv('KESTREL_PUBLIC_CONFIG',raising=False)
    with pytest.raises((RuntimeError,OSError)):settings.load_deployment()
    monkeypatch.setenv('KESTREL_ENV','PUBLIC')
    with pytest.raises(RuntimeError):settings.load_deployment()
    config,_,_=fixture_owner_files(tmp_path,monkeypatch)
    def deny_acl(*args):raise RuntimeError('Synthetic unapproved ACL')
    monkeypatch.setattr(settings,'_windows_private_file',deny_acl)
    with pytest.raises(RuntimeError,match='ACL'):settings.load_deployment()


def test_public_receipt_configuration_and_test_sources_cannot_drift(tmp_path,monkeypatch):
    config,approval,_=fixture_owner_files(tmp_path,monkeypatch)
    receipt=Path(config['receipt_file']);original=receipt.read_bytes();value=json.loads(original);value['all_required_passed']=False;receipt.write_text(settings.canonical(value))
    with pytest.raises(RuntimeError):settings.load_deployment()
    receipt.write_bytes(original)
    (settings.ROOT/'backend/tests/test_fixture.py').write_text('# Changed after recorded acceptance')
    with pytest.raises(RuntimeError):settings.load_deployment()


def test_exact_proxy_hosts_origin_and_forwarding_assertions(public_env):
    _,app,_,token=public_env
    with client(app,token) as http:
        response=http.get('/boundary-fixture',headers={'x-forwarded-host':'attacker.invalid','x-forwarded-proto':'http','x-forwarded-for':'10.0.0.1','forwarded':'host=attacker.invalid','x-demo-user':'root'})
        assert response.status_code==200,response.text
        value=response.json();assert value['host']=='firm.portal.ramijaloudi.com' and value['scheme']=='https' and value['peer']=='203.0.113.20'
        assert not any(key.startswith(('x-forwarded-','x-kestrel-')) or key in {'forwarded','x-demo-user'} for key in value['headers'])
        assert http.get('/health',headers={'host':'FIRM.PORTAL.RAMIJALOUDI.COM:443'}).status_code==200
        for host in ['127.0.0.1','localhost','firm.portal.ramijaloudi.com.attacker.invalid','firm.portal.ramijaloudi.com:444','firm.portal.ramijaloudi.com.']:
            assert http.get('/health',headers={'host':host}).status_code==403
        for origin in ['https://attacker.invalid','https://halden.portal.ramijaloudi.com','http://firm.portal.ramijaloudi.com','https://firm.portal.ramijaloudi.com/path']:
            assert http.get('/health',headers={'origin':origin}).status_code==403
        for key,value in [('x-kestrel-proxy-token','wrong'),('x-kestrel-proto','http'),('x-kestrel-client-ip','203.0.113.1, 127.0.0.1')]:
            assert http.get('/health',headers={key:value}).status_code==403
    with client(app,token,peer='203.0.113.9') as http:assert http.get('/health').status_code==403
    with TestClient(app,base_url='https://firm.portal.ramijaloudi.com') as http:assert http.get('/health',headers=proxy_headers(token)).status_code==403


@pytest.mark.parametrize('key',['host','origin','x-kestrel-proxy-token','x-kestrel-proto','x-kestrel-client-ip'])
def test_duplicate_security_headers_are_rejected(public_env,key):
    _,app,_,token=public_env
    values={'host':'firm.portal.ramijaloudi.com','origin':'https://firm.portal.ramijaloudi.com',**proxy_headers(token)}
    headers=[(k,v) for k,v in values.items()]+[(key,values[key])]
    with client(app,token) as http:assert http.get('/health',headers=headers).status_code==403


def test_public_host_only_sessions_org_csrf_and_local_app_isolation(public_env):
    (env,app,_,token)=public_env;local=env[3]
    with client(app,token) as http:
        response=login(http,'lawyer');assert response.status_code==200,response.text;csrf=response.json()['csrf_token']
        cookie=response.headers['set-cookie'];assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Domain=' not in cookie
        assert http.get('/api/v1/auth/me').json()['organization']=='firm'
        assert http.post('/api/v1/auth/logout',headers={'origin':str(http.base_url).rstrip('/')}).status_code==403
        assert http.post('/api/v1/auth/logout',headers={'origin':str(http.base_url).rstrip('/'),'x-csrf-token':csrf}).status_code==204
    with client(app,token,'castlegate.portal.ramijaloudi.com') as http:
        assert login(http,'lawyer').status_code==401
        assert login(http,'bank').status_code==200
    assert local.state.deployment.mode=='LOCAL' and auth.HOSTS==settings.LOCAL_HOSTS
    with TestClient(local,base_url='https://firm.localhost') as http:assert http.get('/health').status_code==200


def test_public_home_swagger_audience_and_preview_diagnostics_closed(public_env):
    _,app,_,token=public_env
    with client(app,token,'portal.ramijaloudi.com') as http:
        assert http.get('/').status_code==200 and http.get('/site-config').json()['links']['firm']=='https://firm.portal.ramijaloudi.com'
        for path in ['/docs','/openapi.json','/api/v1/auth/me','/portal']:assert http.get(path).status_code==403
    with client(app,token) as http:
        for path in ['/preview','/launch-info','/health/ready','/diagnostics','/debug']:assert http.get(path).status_code==404
        for path in ['/docs','/openapi.json','/swagger/swagger-ui-bundle.js','/swagger-session.js']:assert http.get(path).status_code==401
        assert login(http,'lawyer').status_code==200
        assert http.get('/docs/workflow').status_code==200
    with client(app,token,'castlegate.portal.ramijaloudi.com') as http:
        assert login(http,'bank').status_code==200
        assert http.get('/docs/workflow').status_code==403
        schema=http.get('/openapi.json');assert schema.status_code==200
        assert '/api/v1/financial/query' in schema.json()['paths']
        assert '/api/v1/financial/organization-gate' not in schema.json()['paths']
        assert not any('/api/v1/ddr/' in path or '/api/v1/admin/' in path for path in schema.json()['paths'])


def test_authored_resource_links_map_without_touching_evidence_or_guide_text(public_env):
    _,app,_,token=public_env
    with client(app,token,'admin.portal.ramijaloudi.com') as http:
        assert login(http,'root').status_code==200
        guides=http.get('/api/v1/resources').json()
        assert any('https://admin.portal.ramijaloudi.com/' in link['href'] for guide in guides for link in guide['links'])
        assert not any('.localhost' in link['href'] for guide in guides for link in guide['links'])
    request=SimpleNamespace(app=app)
    assert settings.navigation_url(request,'https://example.invalid/evidence?url=https://firm.localhost:8443/')=='https://example.invalid/evidence?url=https://firm.localhost:8443/'


def test_public_body_bounds_and_approval_revocation(public_env):
    _,app,config,token=public_env
    with client(app,token) as http:
        assert http.post('/body-fixture',content=b'x'*(3*1024*1024)).json()['size']==3*1024*1024
        assert http.post('/body-fixture',content=b'x'*(4*1024*1024+1)).status_code==413
        assert http.post('/body-fixture',content=b'abc',headers={'content-length':'4'}).status_code==400
        Path(config['approval_file']).unlink()
        assert http.get('/health').status_code==503


def test_public_authenticated_synthetic_upload_keeps_existing_per_file_limit(public_env):
    (env,app,_,token)=public_env;ids=env[2]
    with client(app,token) as http:
        signed=login(http,'lawyer');assert signed.status_code==200
        headers={'origin':str(http.base_url).rstrip('/'),'x-csrf-token':signed.json()['csrf_token'],'content-type':'application/octet-stream'}
        query={'matter_id':ids['matter'],'file_name':'synthetic.txt','logical_key':'PUBLIC-FIXTURE','classification':'ordinary','resource_type':'contract','language':'en','governing_law':'unconfirmed','wave':'manual','synthetic':True}
        response=http.post('/api/v1/workflow/documents',params=query,content=b'Synthetic contract for public-boundary fixture only.',headers=headers)
        assert response.status_code==201,response.text
        query['logical_key']='PUBLIC-TOO-BIG'
        assert http.post('/api/v1/workflow/documents',params=query,content=b'x'*(3*1024*1024+1),headers=headers).status_code==413


def test_swagger_full_schema_rechecks_current_audience_after_preparation(public_env,monkeypatch):
    env,app,_,token=public_env
    from kestrel.models import RoleGrant
    from sqlalchemy import delete
    with client(app,token) as http:
        assert login(http,'lawyer').status_code==200
        original=app.openapi;changed=[]
        def revoke():
            value=original()
            if not changed:
                changed.append(True)
                with env[1]() as db:db.execute(delete(RoleGrant).where(RoleGrant.account_id==env[2]['lawyer']));db.commit()
            return value
        monkeypatch.setattr(app,'openapi',revoke)
        assert http.get('/openapi.json').status_code==403


def test_rate_limiter_is_atomic_bounded_and_does_not_evict_active_keys():
    now=[0.0];limiter=BoundedLimiter(capacity=2,clock=lambda:now[0])
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:results=list(pool.map(lambda _:limiter.allow('same',20,60),range(100)))
    assert sum(results)==20 and len(limiter.rows)==1
    assert limiter.allow('second',1,60) and not limiter.allow('third',1,60) and len(limiter.rows)==2
    now[0]=61;assert limiter.allow('third',1,60)


def test_login_database_throttle_updates_are_atomic_under_concurrency(env,monkeypatch):
    _,sessions,_,app=env
    monkeypatch.setattr(auth,'HASHER',SimpleNamespace(verify=lambda *args:False))
    def attempt(_):
        request=SimpleNamespace(app=app,url=SimpleNamespace(hostname='firm.localhost',scheme='https',netloc='firm.localhost'),headers={'origin':'https://firm.localhost'},client=SimpleNamespace(host='127.0.0.1'),cookies={})
        with sessions() as db:
            try:auth.login(db,request,'atomic-unknown-user','synthetic-incorrect-password');return 200
            except HTTPException as error:return error.status_code
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(attempt,range(14)))
    assert results.count(401)==10 and results.count(429)==4
    with sessions() as db:assert db.get(LoginThrottle,auth.digest('account:atomic-unknown-user')).attempts<=10


def test_public_service_entrypoint_cannot_bind_publicly_or_trust_forwarding(public_env,monkeypatch):
    _,app,_,_=public_env
    import kestrel.main as main
    import uvicorn
    from kestrel.public_service import main as public_main
    calls=[]
    monkeypatch.setattr(main,'create_app',lambda:app);monkeypatch.setattr(uvicorn,'run',lambda *args,**kwargs:calls.append(kwargs))
    public_main()
    assert len(calls)==1 and calls[0]['host']=='127.0.0.1' and calls[0]['port']==8000
    assert calls[0]['workers']==1 and calls[0]['proxy_headers'] is False and calls[0]['forwarded_allow_ips']==''


def test_runtime_owner_receipt_or_configuration_change_closes_approved_app(public_env):
    _,app,config,token=public_env
    with client(app,token) as http:
        receipt=Path(config['receipt_file']);original=receipt.read_bytes();receipt.write_bytes(original+b' ')
        assert http.get('/health').status_code==503
        receipt.write_bytes(original)
        path=app.state.deployment.config_file;value=json.loads(path.read_text());value['workers']=2;path.write_text(settings.canonical(value))
        assert http.get('/health').status_code==503


def test_actual_ephemeral_loopback_socket_requires_private_proxy_protocol(public_env):
    import socket
    import threading
    import httpx
    import uvicorn
    _,app,_,token=public_env
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(16);port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,proxy_headers=False,forwarded_allow_ips='',access_log=False,
        log_level='critical',http='h11',ws='none',lifespan='off'))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started and time.monotonic()<deadline:time.sleep(0.01)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=5) as http:
            assert http.get('/health',headers={'host':'firm.portal.ramijaloudi.com','x-forwarded-proto':'https'}).status_code==403
            headers={'host':'firm.portal.ramijaloudi.com',**proxy_headers(token),'x-forwarded-host':'attacker.invalid','x-forwarded-for':'1.2.3.4'}
            response=http.get('/boundary-fixture',headers=headers);assert response.status_code==200,response.text
            assert response.json()['host']=='firm.portal.ramijaloudi.com' and response.json()['scheme']=='https' and response.json()['peer']=='203.0.113.20'
            assert http.get('/health',headers={**headers,'host':'127.0.0.1'}).status_code==403
    finally:
        server.should_exit=True;thread.join(5);sock.close()
        assert not thread.is_alive()
