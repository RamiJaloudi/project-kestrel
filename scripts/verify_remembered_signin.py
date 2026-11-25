"""Explicit local HTTPS smoke: persistent cookies, fresh client, logout, forget."""
import copy
import http.client
import http.cookiejar
import json
from pathlib import Path
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env

def verify():
    settings=read_env()
    context=ssl.create_default_context(cafile=str(root/'.runtime/local-ca.pem'))
    hosts={'admin.localhost','firm.localhost','client.localhost','bank.localhost'}
    class Connection(http.client.HTTPSConnection):
        def connect(self):
            if self.host not in hosts:raise RuntimeError('Smoke host denied')
            self.sock=socket.create_connection(('127.0.0.1',self.port),self.timeout)
            self.sock=context.wrap_socket(self.sock,server_hostname=self.host)
    class Handler(urllib.request.HTTPSHandler):
        def https_open(self,request):return self.do_open(Connection,request)
    def opener(jar):return urllib.request.build_opener(urllib.request.ProxyHandler({}),Handler(),urllib.request.HTTPCookieProcessor(jar))
    for host,username in [('admin.localhost',settings['KESTREL_RAMI_EMAIL']),('firm.localhost','sme01@freshfields.example'),
                           ('client.localhost','client01@halden.example'),('bank.localhost','bank01@castlegate.example')]:
        base='https://'+host+':8443';jar=http.cookiejar.CookieJar();original=opener(jar)
        def call(client,path,data=None,method=None,csrf=''):
            headers={'Origin':base,'X-CSRF-Token':csrf}
            if data is not None:headers['Content-Type']='application/json'
            request=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
            with client.open(request,timeout=8) as response:
                body=response.read();return json.loads(body) if body else None
        login=call(original,'/api/v1/auth/login',{'username':username,'password':settings['KESTREL_DUMMY_PASSWORD'],'remember_me':True})
        assert login['expires_in']==30*86400
        fresh=http.cookiejar.CookieJar()
        for cookie in jar:
            assert cookie.secure and cookie.path=='/' and not cookie.domain_specified and cookie.has_nonstandard_attr('HttpOnly')
            assert not cookie.discard and cookie.expires>time.time()+29*86400
            assert settings['KESTREL_DUMMY_PASSWORD'] not in cookie.value
            fresh.set_cookie(copy.copy(cookie))
        assert len(list(fresh))==2
        reopened=opener(fresh)
        restored=call(reopened,'/api/v1/auth/session',{},method='POST')
        assert restored['identity']['username']==username and restored['csrf_token']==login['csrf_token']
        assert call(reopened,'/api/v1/auth/session',{},method='POST')['csrf_token']==restored['csrf_token']
        assert call(reopened,'/api/v1/auth/preferences')['username']==username
        call(reopened,'/api/v1/auth/logout',{},csrf=restored['csrf_token'])
        try:call(original,'/api/v1/auth/session',{},method='POST')
        except urllib.error.HTTPError as error:assert error.code==401
        else:raise RuntimeError('Revoked cookie remained usable')
        assert call(reopened,'/api/v1/auth/preferences')['username']==username
        call(reopened,'/api/v1/auth/preferences',method='DELETE')
        assert call(reopened,'/api/v1/auth/preferences')['username']==''
        print(host+': remembered sign-in, fresh-client restore, sign-out and forget passed')

if __name__=='__main__':
    try:verify()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('remembered_smoke.failed',component='verification',exception=error)
        print('Remembered sign-in verification failed; sanitized diagnostic '+event['event_id']);sys.exit(1)
