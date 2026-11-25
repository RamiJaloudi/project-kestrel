"""Explicit local smoke test: creates one retained synthetic playbook/job.

Uses the two .env interview accounts through real HTTPS sessions. Never run
automatically at startup. Credentials and input passages are never printed.
"""
import http.cookiejar
import http.client
import json
from pathlib import Path
import ssl
import socket
import sys
import time
import urllib.request
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env

def verify():
    env=read_env()
    context=ssl.create_default_context(cafile=str(root/'.runtime/local-ca.pem'))
    class LoopbackConnection(http.client.HTTPSConnection):
        def connect(self):
            if self.host not in {'admin.localhost','firm.localhost'}:raise RuntimeError('Smoke host denied')
            self.sock=socket.create_connection(('127.0.0.1',self.port),self.timeout)
            self.sock=context.wrap_socket(self.sock,server_hostname=self.host)
    class LoopbackHandler(urllib.request.HTTPSHandler):
        def https_open(self,request):return self.do_open(LoopbackConnection,request)
    class Session:
        def __init__(self,host,username):
            self.base=f'https://{host}:8443'
            self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),LoopbackHandler(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            self.csrf=''
            self.csrf=self.call('/api/v1/auth/login',{'username':username,'password':env['KESTREL_INTERVIEW_PASSWORD']})['csrf_token']
        def call(self,path,data=None):
            headers={'Origin':self.base,'X-CSRF-Token':self.csrf}
            if data is not None:headers['Content-Type']='application/json'
            req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
            with self.opener.open(req,timeout=10) as response:
                content=response.read()
                return json.loads(content) if content else None
    admin=Session('admin.localhost',env['KESTREL_SUMEET_EMAIL'])
    sme=Session('firm.localhost',env['KESTREL_CHRIS_EMAIL'])
    try:
        matters=admin.call('/api/v1/policy-editor/matters')
        matter=next(m['id'] for m in matters if m['name']=='Interview demonstration — Project Skylark')
        name='Synthetic queue runtime verification'
        rows=admin.call('/api/v1/policy-editor?matter_id='+matter)
        version=next((v for v in rows if v['name']==name),None)
        if version is None:
            starter=json.loads((root/'data/playbooks/PB-STARTER-GOVERNED-DRAFT.json').read_text())
            version=admin.call('/api/v1/policy-editor',{'matter_id':matter,'kind':'legal_playbook','name':name,'definition':starter})
        path='/api/v1/policy-editor/'+version['id']
        if version['state']=='draft':
            assert admin.call(path+'/test',{})['passed']
            version=admin.call(path+'/submit',{'expected_revision':version['revision'],'rationale':'Request independent review of synthetic smoke examples'})
        if version['state']=='submitted':
            version=sme.call(path+'/approve',{'expected_revision':version['revision'],'rationale':'Independent synthetic example review for worker verification'})
        if version['state']=='approved':
            version=admin.call(path+'/publish',{'expected_revision':version['revision'],'rationale':'Publish exact reviewed synthetic smoke playbook'})
        assert version['state']=='published'
        job=sme.call('/api/v1/jobs',{'playbook_id':version['id'],'idempotency_key':'runtime-smoke-v1','rationale':'Authorize synthetic embedded examples for cross-process verification'})
        for _ in range(30):
            result=sme.call('/api/v1/jobs/'+job['id'])
            if result['state']=='succeeded':
                assert result['result']['status']=='candidate_only'
                assert any(c['evidence'] for c in result['result']['cases'])
                print('PASS: trusted HTTPS sessions -> independent approval -> durable queue -> separate worker -> retained candidate evidence')
                return
            if result['state'] in {'failed','denied'}:raise RuntimeError('Smoke job did not succeed')
            time.sleep(1)
        raise RuntimeError('Smoke worker timed out; inspect retained diagnostics')
    finally:
        admin.call('/api/v1/auth/logout',{});sme.call('/api/v1/auth/logout',{})

if __name__=='__main__':
    try:verify()
    except Exception as error:
        from kestrel.diagnostics import emit
        row=emit('smoke.failed',component='verification',exception=error)
        print('Verification failed; sanitized diagnostic '+row['event_id']);sys.exit(1)
