"""Optional bounded OpenAI embedding transport. No tools, proxies, redirects or retries."""
import json,math,ssl,urllib.request
from fastapi import HTTPException
from kestrel.adapters.openai_review import configuration
MODEL='text-embedding-3-small'
DIMENSIONS=256
VERSION='text-embedding-3-small:256:unicode1600-v1'

def vector(value):
    if not isinstance(value,list) or len(value)!=DIMENSIONS or any(type(v) not in {int,float} or not math.isfinite(v) or abs(v)>2 for v in value):raise HTTPException(502,'Invalid embedding dimensions or values')
    if not any(value):raise HTTPException(502,'Zero embedding returned')
    return value


def send(texts):
    enabled,key=configuration()
    if not enabled or not key:raise HTTPException(409,'Enable the configured AI provider before semantic retrieval')
    if not 1<=len(texts)<=33 or any(not t.strip() or len(t.encode())>8000 for t in texts) or sum(len(t.encode()) for t in texts)>64000:raise HTTPException(413,'Embedding context exceeds the bounded input limit')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise HTTPException(502,'Embedding provider redirects prohibited')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
    payload={'model':MODEL,'dimensions':DIMENSIONS,'input':texts,'encoding_format':'float'}
    request=urllib.request.Request('https://api.openai.com/v1/embeddings',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with opener.open(request,timeout=30) as response:
        raw=response.read(1024*1024+1)
        if len(raw)>1024*1024:raise HTTPException(502,'Embedding response exceeds bounds')
    result=json.loads(raw)
    if result.get('model')!=MODEL or len(result.get('data',[]))!=len(texts):raise HTTPException(502,'Embedding model/count mismatch')
    rows=sorted(result['data'],key=lambda row:row.get('index',-1))
    if [row.get('index') for row in rows]!=list(range(len(texts))):raise HTTPException(502,'Embedding index mismatch')
    return [vector(row.get('embedding')) for row in rows],result.get('usage',{}).get('prompt_tokens')
