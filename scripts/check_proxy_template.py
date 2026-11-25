"""Offline Caddy adaptation only: no server, TLS provisioning or real proxy token."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BINARY_HASH='2622e239c79df700b0eb92cbd950d1edee365e155a7859f358f0e55f002df591'
CANARY='NONSECRET_OFFLINE_PARSE_CANARY_NOT_AN_APPROVAL_0123456789'
HOSTS={'portal.ramijaloudi.com','firm.portal.ramijaloudi.com','halden.portal.ramijaloudi.com','castlegate.portal.ramijaloudi.com','admin.portal.ramijaloudi.com'}


def walk(value):
    if isinstance(value,dict):
        yield value
        for item in value.values():yield from walk(item)
    elif isinstance(value,list):
        for item in value:yield from walk(item)


def review(binary):
    binary=Path(binary)
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=BINARY_HASH:raise ValueError('Verified official Caddy 2.11.9 Windows x64 binary required')
    template=ROOT/'deployment/Caddyfile.public.example'
    result=subprocess.run([str(binary.resolve()),'adapt','--config',str(template),'--adapter','caddyfile'],
        env={**os.environ,'KESTREL_PROXY_TOKEN':CANARY},capture_output=True,text=True,timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode or len(result.stdout.encode())>1024*1024:raise ValueError('Offline proxy adaptation failed')
    config=json.loads(result.stdout);nodes=list(walk(config));servers=config['apps']['http']['servers']
    if config.get('admin',{}).get('disabled') is not True or config.get('admin',{}).get('config',{}).get('persist',True) is not False:raise ValueError('Owner-only proxy administration contract changed')
    if {listen for server in servers.values() for listen in server['listen']}!={':443',':80'}:raise ValueError('Unexpected proxy listener declaration')
    if any(server.get('strict_sni_host') is not True or not 0<server.get('max_header_bytes',0)<=16384 or set(server.get('protocols',[]))!={'h1','h2'} for server in servers.values()):raise ValueError('Proxy hostname/protocol/header boundary changed')
    host_lists=[node['host'] for node in nodes if isinstance(node.get('host'),list)]
    if len(host_lists)!=2 or any(set(hosts)!=HOSTS for hosts in host_lists):raise ValueError('Proxy hostname list changed')
    proxies=[node for node in nodes if node.get('handler')=='reverse_proxy']
    if len(proxies)!=1 or proxies[0]['upstreams']!=[{'dial':'127.0.0.1:8000'}]:raise ValueError('Exact private upstream required')
    request=proxies[0]['headers']['request'];headers={key.lower():value for key,value in request['set'].items()}
    if set(request['delete'])!={'Forwarded','X-Forwarded-*','X-Real-IP','X-Demo-User','X-Kestrel-*'}:raise ValueError('Untrusted proxy assertions are not stripped')
    if headers!={'host':['{http.request.host}'],'x-kestrel-client-ip':['{http.request.remote.host}'],'x-kestrel-proto':['https'],'x-kestrel-proxy-token':[CANARY]}:raise ValueError('Private protocol is not overwritten from the actual connection')
    if not any(node.get('handler')=='request_body' and node.get('max_size')==4194304 for node in nodes):raise ValueError('Bounded request body required')
    return {'schema':'kestrel-proxy-offline-review-1','version':'2.11.9','binary_sha256':BINARY_HASH,
        'archive_sha256':'ad93112d335ee687100c4c9f11bced16ca590377976b7fe7883882b9e797e472',
        'source':'https://github.com/caddyserver/caddy/releases/tag/v2.11.9',
        'template_sha256':hashlib.sha256(template.read_bytes()).hexdigest(),'hosts':sorted(HOSTS),
        'adapted':True,'admin_disabled':True,'private_upstream':True,'security_headers_checked':True,
        'formatting_warning':bool(result.stderr),'scope':'Parser and static boundary assertions only; no listener, certificate provisioning, DNS, owner approval or actual TLS/proxy validation.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--caddy',default=ROOT/'.runtime/tools/caddy-v2.11.9/caddy.exe',type=Path)
    args=parser.parse_args()
    try:
        receipt=review(args.caddy);target=ROOT/'.runtime/azure/proxy-review.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print(json.dumps(receipt));return 0
    except Exception:
        print('Offline proxy review failed; check the pinned binary and reviewed template. No service was launched and no real token was read.');return 1


if __name__=='__main__':raise SystemExit(main())
