"""Single-worker public boundary; actual loopback proxy proof precedes IP trust."""
import asyncio
import hmac
import ipaddress
import threading
import time
from collections import OrderedDict
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool


class BoundedLimiter:
    def __init__(self,capacity=4096,clock=time.monotonic):
        self.capacity,self.clock=capacity,clock;self.rows=OrderedDict();self.lock=threading.Lock()
    def allow(self,key,limit,seconds):
        with self.lock:
            now=self.clock()
            # At most the fixed capacity is examined; active identities are never
            # evicted to let a new identity bypass a full protection table.
            for old in [k for k,(count,expiry) in self.rows.items() if expiry<=now]:self.rows.pop(old,None)
            value=self.rows.get(key)
            if value is None:
                if len(self.rows)>=self.capacity:return False
                self.rows[key]=(1,now+seconds);return True
            count,expiry=value
            if count>=limit:return False
            self.rows[key]=(count+1,expiry);return True


class PublicBoundary:
    def __init__(self,app,settings):self.app,self.settings=app,settings;self.limiter=BoundedLimiter();self.login_slots=threading.BoundedSemaphore(4)
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            if scope['type']=='websocket':await send({'type':'websocket.close','code':1008});return
            return await self.app(scope,receive,send)
        async def deny(status,detail):
            response=JSONResponse({'detail':detail},status_code=status,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"frame-ancestors 'none'"})
            await response(scope,receive,send)
        if not self.settings.active():return await deny(503,'Public owner approval is closed')
        peer=scope.get('client',('',0))[0]
        if peer not in {'127.0.0.1','::1'}:return await deny(403,'Trusted proxy required')
        headers=scope.get('headers',[])
        if sum(len(k)+len(v) for k,v in headers)>16384:return await deny(431,'Request headers exceed limit')
        values={}
        for key,value in headers:values.setdefault(key.lower(),[]).append(value)
        for key in [b'host',b'origin',b'x-kestrel-proxy-token',b'x-kestrel-proto',b'x-kestrel-client-ip',b'content-length']:
            if len(values.get(key,[]))>1:return await deny(403,'Ambiguous request headers')
        def one(key):return values.get(key,[b''])[0].decode('ascii',errors='replace')
        host=self.settings.normalized_host(one(b'host'))
        token=one(b'x-kestrel-proxy-token')
        if not host or not token.isascii() or not 43<=len(token)<=128 or one(b'x-kestrel-proto')!='https' or not hmac.compare_digest(token,self.settings.proxy_token):return await deny(403,'Trusted HTTPS portal required')
        try:client_ip=str(ipaddress.ip_address(one(b'x-kestrel-client-ip')))
        except ValueError:return await deny(403,'Trusted client address required')
        origin=one(b'origin')
        if origin and not self.settings.origin_matches(origin,host):return await deny(403,'Request origin denied')
        path=scope.get('path','')
        if len(path)>2048 or len(scope.get('query_string',b''))>4096:return await deny(414,'Request target exceeds limit')
        if path.startswith(('/preview','/launch-info','/health/ready','/diagnostics','/debug','/redoc')):return await deny(404,'Not found')
        if self.settings.hosts[host] is None and path.startswith(('/api','/docs','/openapi','/swagger','/admin','/portal')):return await deny(403,'Select an organization portal')
        category='login' if path=='/api/v1/auth/login' else 'api' if path.startswith('/api/') else 'web'
        limit,window={'login':(60,900),'api':(600,60),'web':(1200,60)}[category]
        if not self.limiter.allow((category,client_ip),limit,window):return await deny(429,'Try again later')
        # Drop every ambient forwarding/identity assertion before Request.url or
        # downstream code sees it. The only trusted assertions are the above
        # private protocol, overwritten by the edge from its actual connection.
        scope=dict(scope);scope['headers']=[(k,v) for k,v in headers if k.lower() not in {b'forwarded',b'x-real-ip',b'x-demo-user',b'x-kestrel-proxy-token',b'x-kestrel-proto',b'x-kestrel-client-ip',b'host'} and not k.lower().startswith(b'x-forwarded-')]+[(b'host',host.encode())]
        scope['scheme']='https';scope['client']=(client_ip,0);scope['server']=(host,443);scope['state']=dict(scope.get('state',{}),public_boundary=True)
        request=Request(scope)
        if path.startswith('/swagger/'):
            from kestrel.preview import swagger_access
            from fastapi import HTTPException
            try:await run_in_threadpool(swagger_access,request)
            except HTTPException as error:return await deny(error.status_code,'API explorer authentication required')
        def account_key():
            from kestrel.services import auth
            from fastapi import HTTPException
            with scope['app'].state.sessions() as db:
                try:return auth.authenticate(db,request,check_csrf=False)[0].id
                except HTTPException:return None
        if category=='api' and request.cookies:
            account=await run_in_threadpool(account_key)
            if account and not self.limiter.allow(('account',account),240,60):return await deny(429,'Try again later')
        length=one(b'content-length')
        body_limit=16384 if category=='login' else 4*1024*1024
        if length and b'transfer-encoding' in values:return await deny(400,'Ambiguous request body framing')
        if length and (len(length)>10 or not length.isdecimal() or int(length)>body_limit):return await deny(413,'Request body exceeds limit')
        body=bytearray();size=0;chunk_count=0;deadline=time.monotonic()+20
        try:
            while True:
                message=await asyncio.wait_for(receive(),max(0.001,deadline-time.monotonic()))
                if message['type']=='http.disconnect':return
                chunk=message.get('body',b'');size+=len(chunk);chunk_count+=1
                if size>body_limit:return await deny(413,'Request body exceeds limit')
                if chunk_count>1024:return await deny(413,'Request body framing exceeds limit')
                body.extend(chunk)
                if not message.get('more_body',False):break
        except asyncio.TimeoutError:return await deny(408,'Request body timed out')
        if length and size!=int(length):return await deny(400,'Request body length mismatch')
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:delivered=True;return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        acquired=category=='login' and self.login_slots.acquire(blocking=False)
        if category=='login' and not acquired:return await deny(429,'Sign-in capacity busy; try again later')
        try:await self.app(scope,bounded_receive,send)
        finally:
            if acquired:self.login_slots.release()
