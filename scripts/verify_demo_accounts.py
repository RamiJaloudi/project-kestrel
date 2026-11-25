"""Explicit read-only profile checks through real local HTTPS login/logout."""
import http.client
import http.cookiejar
import json
from pathlib import Path
import socket
import ssl
import sys
import urllib.request
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.demo_setup import PROFILES
from kestrel.localenv import read_env
from kestrel.demo_names import username as profile_username

def verify():
    values=read_env()
    context=ssl.create_default_context(cafile=str(root/'.runtime/local-ca.pem'))
    hosts={'admin.localhost','firm.localhost','client.localhost','bank.localhost'}
    class Connection(http.client.HTTPSConnection):
        def connect(self):
            if self.host not in hosts:raise RuntimeError('Verifier host denied')
            self.sock=socket.create_connection(('127.0.0.1',self.port),self.timeout)
            self.sock=context.wrap_socket(self.sock,server_hostname=self.host)
    class Handler(urllib.request.HTTPSHandler):
        def https_open(self,request):return self.do_open(Connection,request)
    rows=[{**profile,'username':profile_username(profile,index),'password':values['KESTREL_DUMMY_PASSWORD']}
          for profile in PROFILES for index in range(1,4)]
    rows.extend({'username':values[key],'password':values['KESTREL_INTERVIEW_PASSWORD'],'role':role,'host':host,'clean_team':False}
        for key,role,host in [('KESTREL_CHRIS_EMAIL','legal_sme','firm.localhost'),('KESTREL_SUMEET_EMAIL','root_admin','admin.localhost')])
    if values.get('KESTREL_RAMI_EMAIL'):
        rows.append({'username':values['KESTREL_RAMI_EMAIL'],'password':values['KESTREL_DUMMY_PASSWORD'],'role':'root_admin','host':'admin.localhost','clean_team':False})
    fixture=root/'.runtime/wave1-seeded.json'
    if fixture.exists():
        clean_sme=json.loads(fixture.read_text())['clean_sme_username']
        for row in rows:
            if row['username']==clean_sme:row['clean_team']=True
    from kestrel.database import factory,make_engine,database_url
    from kestrel.models import Account
    from sqlalchemy import select
    engine=make_engine(database_url())
    with factory(engine)() as db:
        customized=set(db.scalars(select(Account.username).where(Account.password_customized.is_(True))))
    engine.dispose()
    skipped=sum(row['username'] in customized for row in rows)
    rows=[row for row in rows if row['username'] not in customized]
    for row in rows:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Handler(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        base='https://'+row['host']+':8443';csrf=''
        def request(path,data=None):
            headers={'Origin':base,'X-CSRF-Token':csrf}
            if data is not None:headers['Content-Type']='application/json'
            req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
            with opener.open(req,timeout=10) as response:
                body=response.read();return json.loads(body) if body else None
        csrf=request('/api/v1/auth/login',{'username':row['username'],'password':row['password']})['csrf_token']
        try:
            identity=request('/api/v1/auth/me')
            assert identity['roles']==[row['role']]
            guides=request('/api/v1/resources')
            assert any(g['id']=='clean-team' for g in guides)==row['clean_team']
            if row['role']=='root_admin' and row['username'].startswith('admin'):
                assert any(m['client_matter_number']=='012345-789012' for m in request('/api/v1/validation/matters'))
        finally:request('/api/v1/auth/logout',{})
    assert values['KESTREL_DUMMY_PASSWORD']==values['KESTREL_INTERVIEW_PASSWORD']
    print(f'PASS: {len(rows)} default-password accounts authenticated; {skipped} customized-password accounts skipped. Roles, portals and clean-team guides verified for authenticated accounts.')

if __name__=='__main__':
    try:verify()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('account_verification.failed',component='verification',exception=error)
        print('Account verification failed; sanitized diagnostic '+event['event_id']);sys.exit(1)
