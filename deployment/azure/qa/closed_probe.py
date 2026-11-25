"""Standalone closed-target QA. Never launches the application or writes approvals."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from kestrel import deployment_settings as deployment
from kestrel.public_boundary import PublicBoundary

SCHEMA = 'kestrel-closed-platform-probe-1'
MAX_SECONDS = 900
BIND_HOST, BIND_PORT = '127.0.0.1', 9446
FIELDS = {'schema', 'purpose', 'owner_sid', 'service_sid', 'proxy_sid',
          'proxy_token_file', 'issued_at', 'expires_at', 'release_hash', 'test_suite_hash'}


def fingerprint():
    return {'schema': 'kestrel-closed-probe-fingerprints-1',
            'release_hash': deployment.release_hash(),
            'test_suite_hash': deployment.test_suite_hash(),
            'operational_acceptance': False}


def process_identity():
    """Real OS facts only; there is no non-Windows or administrator fallback."""
    if os.name != 'nt':
        raise RuntimeError('Real Windows service identity required')
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('Nonadministrator service identity required')
    adv, kernel = ctypes.windll.advapi32, ctypes.windll.kernel32
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetTokenInformation.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    token = ctypes.c_void_p()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise RuntimeError('Process token unavailable')
    try:
        size = wintypes.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise RuntimeError('Process identity unavailable')
        sid = wintypes.LPWSTR()
        if not adv.ConvertSidToStringSidW(ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.byref(sid)):
            raise RuntimeError('Process SID unavailable')
        try:
            return sid.value
        finally:
            kernel.LocalFree(sid)
    finally:
        kernel.CloseHandle(token)


def validate_shape(config, now):
    if not isinstance(config, dict) or set(config) != FIELDS:
        raise RuntimeError('Exact closed QA schema required; no approval/receipt fields')
    if config['schema'] != SCHEMA or config['purpose'] != 'closed-synthetic-platform-qa':
        raise RuntimeError('Closed synthetic QA purpose required')
    for key in ('owner_sid', 'service_sid', 'proxy_sid'):
        if not isinstance(config[key], str) or not re.fullmatch(r'S-1-[0-9-]+', config[key]):
            raise RuntimeError('Explicit Windows SIDs required')
    if len({config[k] for k in ('owner_sid', 'service_sid', 'proxy_sid')}) != 3:
        raise RuntimeError('Three distinct identities required')
    if any(type(config[k]) is not int for k in ('issued_at', 'expires_at')) or not config['issued_at'] <= now < config['expires_at'] <= config['issued_at'] + MAX_SECONDS:
        raise RuntimeError('Current QA lease of at most 15 minutes required')
    for key in ('release_hash', 'test_suite_hash'):
        if not isinstance(config[key], str) or not re.fullmatch('[0-9a-f]{64}', config[key]):
            raise RuntimeError('Reviewed source fingerprints required')
    if not isinstance(config['proxy_token_file'], str):
        raise RuntimeError('External QA token path required')


@dataclass(frozen=True)
class Lease:
    path: Path
    config: dict = field(repr=False)
    token_path: Path
    token: str = field(repr=False)
    config_hash: str
    token_hash: str
    deadline: float

    def active(self):
        try:
            return (self.config['issued_at'] <= time.time() < self.config['expires_at'] and time.monotonic() < self.deadline
                    and self.path.stat().st_size <= 32768 and self.token_path.stat().st_size <= 256
                    and deployment.sha(deployment.canonical(deployment._read_json(self.path))) == self.config_hash
                    and deployment.sha(self.token_path.read_bytes()) == self.token_hash)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            return False


def load_lease(path):
    path = deployment._external(path)
    config = deployment._read_json(path)
    now = int(time.time())
    validate_shape(config, now)
    if process_identity() != config['service_sid']:
        raise RuntimeError('Run as the configured application service identity')
    owner, service, proxy = (config[k] for k in ('owner_sid', 'service_sid', 'proxy_sid'))
    token_path = deployment._external(config['proxy_token_file'])
    if token_path == path:
        raise RuntimeError('Separate QA config and token files required')
    deployment._windows_private_file(path, owner, service, {service})
    deployment._windows_private_file(token_path, owner, service, {service, proxy})
    if token_path.stat().st_size > 256:
        raise RuntimeError('QA token file exceeds bound')
    token_bytes = token_path.read_bytes()
    token = token_bytes.decode('ascii').strip()
    if not re.fullmatch('[A-Za-z0-9_-]{43,128}', token):
        raise RuntimeError('Separate random QA proxy token required')
    if config['release_hash'] != deployment.release_hash() or config['test_suite_hash'] != deployment.test_suite_hash():
        raise RuntimeError('QA lease does not match reviewed source/build')
    return Lease(path, config, token_path, token, deployment.sha(deployment.canonical(config)),
                 deployment.sha(token_bytes), time.monotonic() + config['expires_at'] - now)


def verify_platform(lease):
    # Recheck actual identity/DACLs immediately before issuing platform evidence.
    lease = load_lease(lease.path)
    if not lease.active():
        raise RuntimeError('QA lease closed')
    from kestrel.adapters.provider_secrets import crypt
    marker = secrets.token_bytes(48)
    protected = crypt(marker, True)
    if not protected or protected == marker or crypt(protected, False) != marker:
        raise RuntimeError('Synthetic CurrentUser DPAPI round trip failed')
    if not lease.active():
        raise RuntimeError('QA lease closed during verification')
    return {'schema': 'kestrel-closed-platform-evidence-1', 'purpose': 'closed-synthetic-platform-qa',
            'verified_at': int(time.time()), 'service_sid': lease.config['service_sid'],
            'qa_lease_hash': lease.config_hash,
            'release_hash': lease.config['release_hash'], 'test_suite_hash': lease.config['test_suite_hash'],
            'real_windows_identity_and_two_file_acls': True, 'synthetic_same_profile_dpapi_roundtrip': True,
            'operational_acceptance': False, 'pending': ['ancestor_directory_control', 'proxy_process_identity',
                'cross_identity_dpapi_denial', 'archive_transfer', 'target_restore', 'tls_proxy',
                'actual_api_worker_caddy_pg_services', 'crash_and_reboot', 'public_owner_approval', 'external_ingress']}


class QABoundarySettings:
    """Test composition only. Production load_deployment never constructs this."""
    def __init__(self, lease):
        self.lease = lease
        self.proxy_token = lease.token
        self._host_policy = deployment.DeploymentSettings(mode='PUBLIC_DEMO')
    @property
    def hosts(self):
        return dict(deployment.PUBLIC_HOSTS)
    def active(self):
        return self.lease.active()
    def normalized_host(self, raw):
        return self._host_policy.normalized_host(raw)
    def origin_matches(self, origin, host):
        return self._host_policy.origin_matches(origin, host)


async def respond(scope, receive, send, status, value):
    from starlette.responses import JSONResponse
    response = JSONResponse(value, status_code=status, headers={'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff', 'X-Kestrel-Closed-QA': 'true'})
    await response(scope, receive, send)


def build_probe(lease):
    async def minimal(scope, receive, send):
        # PublicBoundary has already buffered and bounded the body. Never reflect
        # request contents, credentials, arbitrary headers or source material.
        await respond(scope, receive, send, 200, {'mode': 'CLOSED_PLATFORM_QA',
            'synthetic_only': True, 'operational_acceptance': False,
            'host': scope['server'][0], 'scheme': scope['scheme'], 'peer': scope['client'][0],
            'ambient_identity_or_forwarding_present': any(k.lower() in {b'forwarded', b'x-real-ip', b'x-demo-user'}
                or k.lower().startswith((b'x-forwarded-', b'x-kestrel-')) for k, _ in scope['headers'])})
    boundary = PublicBoundary(minimal, QABoundarySettings(lease))
    async def closed(scope, receive, send):
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
        if scope['type'] != 'http':
            if scope['type'] == 'websocket':
                await send({'type': 'websocket.close', 'code': 1008})
            return
        if not lease.active():
            return await respond(scope, receive, send, 503, {'detail': 'Closed QA lease expired or changed'})
        headers = scope.get('headers', [])
        client_ips = [v for k, v in headers if k.lower() == b'x-kestrel-client-ip']
        try:
            loopback = len(client_ips) == 1 and ipaddress.ip_address(client_ips[0].decode('ascii')).is_loopback
        except (ValueError, UnicodeError):
            loopback = False
        if scope.get('client', ('', 0))[0] != BIND_HOST or not loopback:
            return await respond(scope, receive, send, 403, {'detail': 'Closed target loopback only'})
        # Reject cookies before PublicBoundary can consider account DB throttles.
        if any(k.lower() in {b'cookie', b'authorization'} for k, _ in headers):
            return await respond(scope, receive, send, 403, {'detail': 'No credentials in platform probe'})
        if scope.get('path') != '/closed-probe' or scope.get('query_string', b'') or scope.get('method') not in {'GET', 'POST'}:
            return await respond(scope, receive, send, 404, {'detail': 'No application routes'})
        await boundary(scope, receive, send)
    return closed


def serve(lease):
    import uvicorn
    if not lease.active():
        raise RuntimeError('QA lease closed')
    server = uvicorn.Server(uvicorn.Config(build_probe(lease), host=BIND_HOST, port=BIND_PORT,
        workers=1, proxy_headers=False, forwarded_allow_ips='', access_log=False, server_header=False,
        ws='none', http='h11', lifespan='off', limit_concurrency=8, timeout_keep_alive=5,
        timeout_graceful_shutdown=5, h11_max_incomplete_event_size=16384))
    timer = threading.Timer(max(0.001, lease.deadline - time.monotonic()), lambda: setattr(server, 'should_exit', True))
    timer.daemon = True
    timer.start()
    try:
        server.run()
    finally:
        timer.cancel()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('fingerprint')
    for command in ('verify-platform', 'serve'):
        item = sub.add_parser(command)
        item.add_argument('--config', required=True)
        if command == 'verify-platform':
            item.add_argument('--evidence', required=True)
    args = parser.parse_args()
    if args.command == 'fingerprint':
        print(json.dumps(fingerprint(), indent=2))
        return
    lease = load_lease(args.config)
    if args.command == 'serve':
        serve(lease)
        return
    evidence = verify_platform(lease)
    # Exclusive creation only. Do not overwrite arbitrary operator files.
    with Path(args.evidence).open('x', encoding='utf-8') as stream:
        json.dump(evidence, stream, indent=2)
        stream.write('\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # A raw exception may include local paths. Evidence is success-only;
        # failures remain a nonzero exit and are never converted to pass files.
        print('Closed QA probe failed; review target prerequisites privately.', file=sys.stderr)
        raise SystemExit(1)
