"""Loopback-only HTTP link redirector. Never serves accounts or API content."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from kestrel.services.auth import HOSTS
from kestrel.diagnostics import activity

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)

@app.middleware('http')
async def redirect_links(request:Request,call_next):
    peer=request.client.host if request.client else ''
    if request.url.hostname not in HOSTS or peer not in {'127.0.0.1','::1','testclient'}:
        return JSONResponse({'detail':'Local host required'},status_code=403)
    if request.method not in {'GET','HEAD'}:
        return JSONResponse({'detail':'Send authenticated requests directly over HTTPS'},status_code=400,headers={'Cache-Control':'no-store'})
    # URL host is allowlisted; forwarded headers are deliberately ignored.
    target=request.url.replace(scheme='https',netloc=f'{request.url.hostname}:8443')
    if not request.url.path.startswith('/health'):
        activity('http','link.redirect',method=request.method,status=308,route='local HTTPS link',duration_ms=0)
    return RedirectResponse(str(target),status_code=308,headers={'Cache-Control':'no-store'})
