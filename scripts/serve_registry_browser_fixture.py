"""Synthetic-only, isolated registry browser QA; never a production launcher.

Run with the project's Python environment from the repository root:

    python scripts/serve_registry_browser_fixture.py prepare
    python scripts/serve_registry_browser_fixture.py serve --fixture <printed directory>
    python scripts/serve_registry_browser_fixture.py inspect --fixture <directory>
    python scripts/serve_registry_browser_fixture.py advance --fixture <directory>

Optional fixture-only receipt-loss exercise:

    python scripts/serve_registry_browser_fixture.py serve --fixture <directory> --lose-client-receipt-once

That flag replaces exactly one successful normal client-creation response with
503, after the real authenticated route has committed. It adds no route or auth
exception and must only be used for the isolated unknown-outcome browser check.

Preparation allocates a fresh UUID directory under .runtime and migrates only its
SQLite database through the real Alembic head. Serving is foreground-only, on
127.0.0.1:9444, with the existing local TLS files and unchanged application host,
deployment, authentication, CSRF and policy checks. Only this helper process uses
distinct QA cookie names. No workers, identity overrides or control routes exist.

The browser uses the first synthetic Root account. The advance command signs in
normally as the second Root and changes the synthetic lawyer's assignment using
the existing optimistic command. It verifies the expected fixture identity and
matter before writing. The standard dummy test password is deliberately public.

Stop the owned foreground server with Ctrl+C after QA; its maximum lifetime is
30 minutes by default. Retain the UUID directory, database, manifest and logs.
No .env, main database, main session cookie, launcher or production source is
changed. Application navigation links to port 8443 remain unchanged: stay in the
fixture's relative Registry navigation on port 9444 during this bounded check.
"""
from __future__ import annotations

import argparse
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import threading
import time
from urllib.parse import urlencode
import uuid


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
HOST = 'admin.localhost'
PORT = 9444
ORIGIN = f'https://{HOST}:{PORT}'
COOKIE = '__Host-kestrel_registry_qa_session'
USERNAME_COOKIE = '__Host-kestrel_registry_qa_username'
PASSWORD = 'synthetic-test-only-passphrase'
SCHEMA = 'kestrel-registry-browser-qa-1'
ACCOUNTS = {
    'browser_root': ('registry.qa.browser.root@example.test', ['root_admin']),
    'peer_root': ('registry.qa.peer.root@example.test', ['root_admin']),
    'lawyer': ('registry.qa.lawyer@example.test', ['firm_lawyer']),
}


def require_local_environment():
    if os.environ.get('KESTREL_ENV', 'LOCAL') != 'LOCAL':
        raise RuntimeError('This synthetic fixture requires the existing LOCAL deployment mode')


def write_json(path: Path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def configure_fixture(directory: Path):
    """Bind this process to the proven fixture before importing the application."""
    require_local_environment()
    os.environ['KESTREL_DATABASE_URL'] = 'sqlite:///' + (directory / 'registry-qa.sqlite3').as_posix()
    os.environ['KESTREL_LOG_DIR'] = str(directory / 'logs')
    os.environ['KESTREL_COMPONENT'] = 'registry-browser-qa'
    sys.path.insert(0, str(ROOT / 'backend'))


def load_fixture(value: str):
    candidate = Path(value)
    if candidate.name == 'fixture.json':
        candidate = candidate.parent
    directory = candidate.resolve(strict=True)
    if directory.parent != RUNTIME.resolve() or not directory.name.startswith('registry-browser-qa-'):
        raise RuntimeError('Only an owned .runtime/registry-browser-qa-UUID fixture is accepted')
    suffix = directory.name.removeprefix('registry-browser-qa-')
    if str(uuid.UUID(suffix)) != suffix or candidate.is_symlink():
        raise RuntimeError('A canonical UUID fixture directory is required')
    manifest_path = directory / 'fixture.json'
    if manifest_path.is_symlink():
        raise RuntimeError('A regular fixture manifest is required')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    expected = {'schema': SCHEMA, 'synthetic_only': True, 'fixture_id': suffix,
                'origin': ORIGIN, 'cookie': COOKIE, 'username_cookie': USERNAME_COOKIE}
    if any(manifest.get(key) != item for key, item in expected.items()):
        raise RuntimeError('The fixture manifest does not match this bounded QA helper')
    database = directory / 'registry-qa.sqlite3'
    if not database.is_file() or database.is_symlink():
        raise RuntimeError('The fixture SQLite database is unavailable')
    for key, (username, roles) in ACCOUNTS.items():
        entry = manifest.get('accounts', {}).get(key, {})
        if entry.get('username') != username or entry.get('roles') != roles or not isinstance(entry.get('id'), str):
            raise RuntimeError('The fixture accounts could not be verified')
    if manifest.get('password') != PASSWORD or set(manifest.get('matters', {})) != {'validated', 'pending'}:
        raise RuntimeError('The fixture metadata could not be verified')
    return directory, manifest


def prepare():
    require_local_environment()
    fixture_id = str(uuid.uuid4())
    directory = RUNTIME / ('registry-browser-qa-' + fixture_id)
    directory.mkdir(parents=True, exist_ok=False)
    configure_fixture(directory)
    from alembic import command
    from alembic.config import Config
    from kestrel.bootstrap import provision
    from kestrel.database import make_engine, factory
    from kestrel.models import Client, Matter, MatterAssignment, MatterValidation
    from kestrel.services import auth

    # The environment override is process-local and precedes Alembic env.py.
    command.upgrade(Config(str(ROOT / 'backend' / 'alembic.ini')), 'head')
    engine = make_engine(os.environ['KESTREL_DATABASE_URL'])
    sessions = factory(engine)
    manifest = {'schema': SCHEMA, 'synthetic_only': True, 'fixture_id': fixture_id,
                'origin': ORIGIN, 'cookie': COOKIE, 'username_cookie': USERNAME_COOKIE,
                'password': PASSWORD, 'accounts': {}, 'matters': {},
                'portal': ORIGIN + '/portal?view=Registry', 'created_at': int(time.time())}
    try:
        with sessions() as db:
            accounts = {}
            for key, (username, roles) in ACCOUNTS.items():
                account = provision(db, username, 'firm', roles, PASSWORD)
                accounts[key] = account
                manifest['accounts'][key] = {'id': account.id, 'username': username, 'roles': roles}
            client = Client(name='Synthetic isolated registry browser QA client', client_number='012345',
                            created_by=accounts['browser_root'].id)
            db.add(client)
            db.flush()
            manifest['client'] = {'id': client.id, 'name': client.name, 'client_number': client.client_number}
            now = auth.clock()
            for status, number in [('validated', '789012'), ('pending', '789013')]:
                matter = Matter(name=f'Synthetic isolated registry QA — {status}')
                db.add(matter)
                db.flush()
                db.add(MatterValidation(matter_id=matter.id, client_id=client.id, status=status,
                                        matter_number=number, revision=1))
                for account in accounts.values():
                    db.add(MatterAssignment(account_id=account.id, matter_id=matter.id,
                                            starts_at=now - 60, expires_at=now + 14 * 86400, revoked=False))
                manifest['matters'][status] = {'id': matter.id, 'name': matter.name,
                                              'matter_number': number, 'status': status, 'revision': 1}
            db.commit()
        write_json(directory / 'fixture.json', manifest)
    finally:
        engine.dispose()
    print(json.dumps({'fixture_directory': str(directory), **manifest}, indent=2, sort_keys=True), flush=True)


def serve(directory: Path, manifest: dict, lifetime: int, lose_client_receipt_once: bool):
    configure_fixture(directory)
    certificate, key = RUNTIME / 'local.pem', RUNTIME / 'local.key'
    if not certificate.is_file() or not key.is_file() or not (RUNTIME / 'local-ca.pem').is_file():
        raise RuntimeError('Existing local certificate, key and CA are required; no TLS fallback exists')
    if not (ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        raise RuntimeError('Build the intended frontend before starting this synthetic QA server')
    # Only this isolated server process uses different cookie names. The auth
    # module's dynamic cookie access preserves all normal session/CSRF behavior.
    from kestrel.services import auth
    auth.COOKIE = COOKIE
    auth.USERNAME_COOKIE = USERNAME_COOKIE
    from kestrel.database import make_engine
    from kestrel.diagnostics import configure_console
    from kestrel.main import create_app
    import uvicorn

    engine = make_engine(os.environ['KESTREL_DATABASE_URL'])
    app = create_app(engine)
    if app.state.deployment.public or HOST not in app.state.deployment.hosts:
        raise RuntimeError('The unchanged local deployment must allow the QA hostname')
    if lose_client_receipt_once:
        from fastapi.responses import JSONResponse
        from kestrel.diagnostics import emit
        lost = False

        @app.middleware('http')
        async def lose_one_committed_client_receipt(request, call_next):
            nonlocal lost
            response = await call_next(request)
            if not lost and request.method == 'POST' and request.url.path == '/api/v1/validation/clients' and response.status_code == 201:
                lost = True
                emit('fixture.client_receipt_withheld', component='registry-browser-qa', status=503)
                return JSONResponse({'detail': 'Synthetic QA: a committed client receipt was withheld once; reload and inspect the registry.'},
                                    status_code=503, headers={'Cache-Control': 'no-store'})
            return response
    configure_console()
    configuration = uvicorn.Config(app, host='127.0.0.1', port=PORT, workers=1,
                                   proxy_headers=False, access_log=False, log_config=None,
                                   ssl_certfile=str(certificate), ssl_keyfile=str(key))
    server = uvicorn.Server(configuration)
    expiry = threading.Timer(lifetime, lambda: setattr(server, 'should_exit', True))
    expiry.daemon = True
    status = {'schema': SCHEMA, 'fixture_id': manifest['fixture_id'], 'pid': os.getpid(),
              'origin': ORIGIN, 'started_at': int(time.time()), 'state': 'starting',
              'max_lifetime_seconds': lifetime, 'lose_client_receipt_once': lose_client_receipt_once}
    write_json(directory / 'server-status.json', status)
    print(json.dumps({'synthetic_only': True, 'fixture_directory': str(directory),
                      'portal': manifest['portal'], 'accounts': manifest['accounts'],
                      'password': PASSWORD, 'lose_client_receipt_once': lose_client_receipt_once,
                      'stop': 'Ctrl+C in this owned foreground session'}, indent=2), flush=True)
    expiry.start()
    try:
        server.run()
    finally:
        expiry.cancel()
        engine.dispose()
        status.update(state='stopped', stopped_at=int(time.time()))
        write_json(directory / 'server-status.json', status)


class FixtureConnection(http.client.HTTPSConnection):
    """Keep TLS hostname validation while pinning the TCP peer to loopback."""
    def connect(self):
        raw = socket.create_connection(('127.0.0.1', PORT), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=HOST)
        except BaseException:
            raw.close()
            raise


class FixtureClient:
    def __init__(self):
        self.context = ssl.create_default_context(cafile=str(RUNTIME / 'local-ca.pem'))
        self.cookie = ''
        self.csrf = ''

    def request(self, method: str, path: str, body=None):
        connection = FixtureConnection(HOST, PORT, context=self.context, timeout=20)
        headers = {'Host': f'{HOST}:{PORT}', 'Origin': ORIGIN}
        if self.cookie:
            headers['Cookie'] = COOKIE + '=' + self.cookie
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        try:
            connection.request(method, '/api/v1' + path,
                               body=None if body is None else json.dumps(body), headers=headers)
            response = connection.getresponse()
            raw = response.read()
            for name, value in response.getheaders():
                if name.lower() != 'set-cookie':
                    continue
                cookies = SimpleCookie()
                cookies.load(value)
                if set(cookies) - {COOKIE, USERNAME_COOKIE}:
                    raise RuntimeError('Unexpected cookie namespace; this is not the isolated QA server')
                if COOKIE in cookies:
                    self.cookie = cookies[COOKIE].value
            if not 200 <= response.status < 300:
                raise RuntimeError(f'Fixture API {method} {path.split("?")[0]} returned HTTP {response.status}')
            return None if not raw else json.loads(raw)
        finally:
            connection.close()

    def login_peer(self, manifest):
        result = self.request('POST', '/auth/login',
                              {'username': ACCOUNTS['peer_root'][0], 'password': PASSWORD})
        if not self.cookie or not isinstance(result, dict) or not isinstance(result.get('csrf_token'), str):
            raise RuntimeError('A normal fixture session could not be established')
        self.csrf = result['csrf_token']
        identity = self.request('GET', '/auth/me')
        if identity.get('id') != manifest['accounts']['peer_root']['id'] or identity.get('roles') != ['root_admin']:
            raise RuntimeError('Refusing to act: the server identity is not this fixture peer Root')

    def logout(self):
        if self.cookie and self.csrf:
            self.request('POST', '/auth/logout', {})


def peer_action(directory: Path, manifest: dict, status: str, advance: bool):
    require_local_environment()
    client = FixtureClient()
    try:
        client.login_peer(manifest)
        rows = client.request('GET', '/validation/matters')
        expected_id = manifest['matters'][status]['id']
        matching = [row for row in rows if row.get('matter_id') == expected_id]
        if len(matching) != 1 or matching[0].get('client_number') != '012345':
            raise RuntimeError('Refusing to act: the expected synthetic matter is not permitted')
        revision = matching[0]['revision']
        base = '/validation/matters/' + expected_id
        context = client.request('GET', base + '/context?' + urlencode({'revision': revision}))
        target = client.request('GET', base + '/access-target?' + urlencode(
            {'revision': revision, 'username': ACCOUNTS['lawyer'][0]}))
        if context.get('matter_id') != expected_id or context.get('revision') != revision or \
                target.get('account_id') != manifest['accounts']['lawyer']['id'] or \
                target.get('matter_revision') != revision or target.get('blocked') is not False:
            raise RuntimeError('Refusing to act: the pinned synthetic matter/target context did not match')
        output = {'synthetic_only': True, 'fixture_id': manifest['fixture_id'],
                  'operation': 'advance' if advance else 'inspect', 'matter_id': expected_id,
                  'matter_status': context['validation_status'], 'before_revision': revision,
                  'target_id': target['account_id'], 'before_assigned': target['assigned']}
        if advance:
            receipt = client.request('POST', base + '/access', {
                'username': target['username'], 'assigned': not target['assigned'], 'blocked': target['blocked'],
                'days': 30, 'expected_revision': revision,
                'rationale': 'Synthetic isolated browser QA: peer Root changes assignment to advance the registry CAS revision.',
            })
            if receipt.get('revision') != revision + 1:
                raise RuntimeError('The synthetic command receipt is uncertain; inspect before any further command')
            after = client.request('GET', base + '/context?' + urlencode({'revision': receipt['revision']}))
            output['after_revision'] = after['revision']
            output['after_assigned'] = not target['assigned']
        write_json(directory / ('peer-' + output['operation'] + '-' + str(uuid.uuid4()) + '.json'), output)
        print(json.dumps(output, indent=2, sort_keys=True), flush=True)
    finally:
        try:
            client.logout()
        except Exception:
            print('Synthetic fixture logout could not be confirmed; no command was retried.', file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['prepare', 'serve', 'inspect', 'advance'])
    parser.add_argument('--fixture', help='Owned UUID directory or its fixture.json; required except for prepare')
    parser.add_argument('--matter', choices=['validated', 'pending'], default='validated')
    parser.add_argument('--lifetime-seconds', type=int, default=1800,
                        help='Foreground server lifetime, 60–3600 seconds; default 1800')
    parser.add_argument('--lose-client-receipt-once', action='store_true',
                        help='serve only: replace the first committed client POST 201 receipt with a synthetic 503')
    args = parser.parse_args()
    if not 60 <= args.lifetime_seconds <= 3600:
        parser.error('--lifetime-seconds must be between 60 and 3600')
    if args.lose_client_receipt_once and args.action != 'serve':
        parser.error('--lose-client-receipt-once is restricted to the isolated serve command')
    if args.action == 'prepare':
        if args.fixture:
            parser.error('prepare always allocates a new UUID directory; do not supply --fixture')
        prepare()
        return
    if not args.fixture:
        parser.error('--fixture is required for serve/inspect/advance')
    directory, manifest = load_fixture(args.fixture)
    if args.action == 'serve':
        serve(directory, manifest, args.lifetime_seconds, args.lose_client_receipt_once)
    else:
        peer_action(directory, manifest, args.matter, args.action == 'advance')


if __name__ == '__main__':
    main()
