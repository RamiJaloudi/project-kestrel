"""Loopback-only client for explicit synthetic operator smoke/seed operations."""
import http.client
import http.cookiejar
import json
from pathlib import Path
import socket
import ssl
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
HOSTS={'admin.localhost','firm.localhost','client.localhost','bank.localhost'}

class LocalAPI:
    def __init__(self,host,username,password,remember=False):
        if host not in HOSTS:raise ValueError('Local portal host required')
        context=ssl.create_default_context(cafile=str(ROOT/'.runtime/local-ca.pem'))
        class Connection(http.client.HTTPSConnection):
            def connect(connection):
                if connection.host not in HOSTS:raise ValueError('Local API target denied')
                connection.sock=socket.create_connection(('127.0.0.1',connection.port),connection.timeout)
                connection.sock=context.wrap_socket(connection.sock,server_hostname=connection.host)
        class Handler(urllib.request.HTTPSHandler):
            def https_open(handler,request):return handler.do_open(Connection,request)
        self.base='https://'+host+':8443';self.csrf=''
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Handler(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf=self.call('/api/v1/auth/login',{'username':username,'password':password,'remember_me':remember})['csrf_token']

    def call(self,path,data=None,method=None,binary=None):
        headers={'Origin':self.base,'X-CSRF-Token':self.csrf}
        body=None
        if binary is not None:headers['Content-Type']='application/octet-stream';body=binary
        elif data is not None:headers['Content-Type']='application/json';body=json.dumps(data).encode()
        request=urllib.request.Request(self.base+path,data=body,headers=headers,method=method)
        with self.opener.open(request,timeout=60) as response:
            content=response.read();return json.loads(content) if content else None

    def close(self):self.call('/api/v1/auth/logout',{})
