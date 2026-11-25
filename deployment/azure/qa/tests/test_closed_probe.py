"""Probe-only tests: no DB, service installation, public listener or pass receipts."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest
from starlette.testclient import TestClient

FILE = Path(__file__).resolve().parents[1] / 'closed_probe.py'
spec = importlib.util.spec_from_file_location('kestrel_closed_probe_qa', FILE)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def config():
    now = int(time.time())
    return {'schema': probe.SCHEMA, 'purpose': 'closed-synthetic-platform-qa',
        'owner_sid': 'S-1-5-21-100', 'service_sid': 'S-1-5-21-101', 'proxy_sid': 'S-1-5-21-102',
        'proxy_token_file': 'synthetic-only-unused-token-path', 'issued_at': now,
        'expires_at': now + 60, 'release_hash': 'a' * 64, 'test_suite_hash': 'b' * 64}


@pytest.fixture
def lease(tmp_path):
    # Component fixture only. Never calls or mocks real platform verification and
    # never claims OS identity, DACLs, TLS or operational acceptance.
    value = config()
    token = 'synthetic_closed_qa_token_' + 'x' * 43
    token_path = tmp_path / 'qa-token'
    token_path.write_text(token, encoding='ascii')
    value['proxy_token_file'] = str(token_path)
    path = tmp_path / 'qa-lease.json'
    path.write_text(probe.deployment.canonical(value), encoding='utf-8')
    return probe.Lease(path, value, token_path, token,
        probe.deployment.sha(probe.deployment.canonical(value)),
        probe.deployment.sha(token_path.read_bytes()), time.monotonic() + 60)


def proof(lease, **changes):
    return {'host': 'firm.portal.ramijaloudi.com', 'x-kestrel-proxy-token': lease.token,
        'x-kestrel-proto': 'https', 'x-kestrel-client-ip': '127.0.0.1', **changes}


def client(lease, peer='127.0.0.1'):
    return TestClient(probe.build_probe(lease), base_url='https://firm.portal.ramijaloudi.com',
        client=(peer, 35000), headers=proof(lease))


def test_exact_separate_lease_shape_and_expiry():
    value = config()
    probe.validate_shape(value, value['issued_at'])
    for field, replacement in [('schema', 'kestrel-public-acceptance-1'),
            ('purpose', 'approve-public-synthetic-demo'), ('service_sid', value['owner_sid']),
            ('issued_at', True), ('expires_at', value['issued_at']),
            ('release_hash', 'unknown'), ('test_suite_hash', 1), ('proxy_token_file', None)]:
        with pytest.raises(RuntimeError):
            probe.validate_shape({**value, field: replacement}, value['issued_at'])
    for extra in ('all_required_passed', 'approval_file', 'receipt_file', 'backend_host'):
        with pytest.raises(RuntimeError):
            probe.validate_shape({**value, extra: True}, value['issued_at'])
    with pytest.raises(RuntimeError):
        probe.validate_shape({**value, 'expires_at': value['issued_at'] + 901}, value['issued_at'])
    with pytest.raises(RuntimeError):
        probe.validate_shape(value, value['issued_at'] - 1)


def test_closed_mode_is_not_accepted_by_production_loader(monkeypatch):
    monkeypatch.setenv('KESTREL_ENV', 'CLOSED_PLATFORM_QA')
    with pytest.raises(RuntimeError):
        probe.deployment.load_deployment()


def test_lease_changes_close_component(lease):
    assert lease.active()
    original = lease.token_path.read_bytes()
    lease.token_path.write_bytes(original + b'x')
    assert not lease.active()
    lease.token_path.write_bytes(original)
    assert lease.active()
    lease.path.write_text('{}')
    assert not lease.active()


def test_lease_clock_and_monotonic_deadlines_close(lease, monkeypatch):
    monkeypatch.setattr(probe.time, 'time', lambda: lease.config['expires_at'])
    assert not lease.active()
    monkeypatch.setattr(probe.time, 'time', lambda: lease.config['issued_at'] - 1)
    assert not lease.active()
    monkeypatch.setattr(probe.time, 'time', lambda: lease.config['issued_at'])
    monkeypatch.setattr(probe.time, 'monotonic', lambda: lease.deadline)
    assert not lease.active()


def test_minimal_route_and_forwarded_assertion_removal(lease):
    with client(lease) as http:
        response = http.get('/closed-probe', headers={'forwarded': 'host=bad.invalid',
            'x-forwarded-host': 'bad.invalid', 'x-forwarded-for': '203.0.113.1',
            'x-real-ip': '203.0.113.2', 'x-demo-user': 'root'})
        assert response.status_code == 200
        assert response.json() == {'mode': 'CLOSED_PLATFORM_QA', 'synthetic_only': True,
            'operational_acceptance': False, 'host': 'firm.portal.ramijaloudi.com',
            'scheme': 'https', 'peer': '127.0.0.1', 'ambient_identity_or_forwarding_present': False}
        assert response.headers['x-kestrel-closed-qa'] == 'true'
        assert response.headers['cache-control'] == 'no-store'
        for path in ['/health', '/site-config', '/docs', '/api/v1/auth/login', '/api/v1/workflow/documents', '/closed-probe?value=private']:
            assert http.get(path).status_code == 404
        assert http.delete('/closed-probe').status_code == 404


@pytest.mark.parametrize('peer,original', [('203.0.113.1', '127.0.0.1'), ('::1', '127.0.0.1'),
    ('testclient', '127.0.0.1'), ('127.0.0.1', '203.0.113.2'), ('127.0.0.1', 'invalid')])
def test_outer_envelope_denies_non_target_connections(lease, peer, original):
    with client(lease, peer) as http:
        assert http.get('/closed-probe', headers={'x-kestrel-client-ip': original}).status_code == 403


def test_token_host_origin_and_credentials_are_denied(lease):
    with client(lease) as http:
        for host in ['127.0.0.1', 'localhost', 'firm.portal.ramijaloudi.com.attacker.invalid',
                'firm.portal.ramijaloudi.com:9446', 'firm.portal.ramijaloudi.com.']:
            assert http.get('/closed-probe', headers={'host': host}).status_code == 403
        for headers in [{'x-kestrel-proxy-token': ''}, {'x-kestrel-proxy-token': 'wrong'},
                {'x-kestrel-proto': 'http'}, {'origin': 'https://halden.portal.ramijaloudi.com'},
                {'origin': 'http://firm.portal.ramijaloudi.com'}, {'cookie': 'session=anything'},
                {'authorization': 'Bearer anything'}]:
            assert http.get('/closed-probe', headers=headers).status_code == 403
        assert http.get('/closed-probe', headers={'host': 'FIRM.PORTAL.RAMIJALOUDI.COM:443'}).status_code == 200
        lease.token_path.unlink()
        assert http.get('/closed-probe').status_code == 503


@pytest.mark.parametrize('duplicate', ['host', 'origin', 'x-kestrel-proxy-token', 'x-kestrel-proto', 'x-kestrel-client-ip'])
def test_duplicate_security_headers_denied(lease, duplicate):
    values = {**proof(lease), 'origin': 'https://firm.portal.ramijaloudi.com'}
    with client(lease) as http:
        assert http.get('/closed-probe', headers=[*values.items(), (duplicate, values[duplicate])]).status_code == 403


def test_existing_boundary_body_and_header_bounds(lease):
    with client(lease) as http:
        assert http.post('/closed-probe', content=b'synthetic').status_code == 200
        assert http.post('/closed-probe', content=b'x' * (4 * 1024 * 1024 + 1)).status_code == 413
        assert http.get('/closed-probe', headers={'x-test-padding': 'x' * 17000}).status_code == 431


def test_serve_options_fixed_without_opening_socket(lease, monkeypatch):
    import uvicorn
    calls = []
    class Server:
        def __init__(self, configuration):
            calls.append(configuration)
        def run(self):
            pass
    monkeypatch.setattr(uvicorn, 'Server', Server)
    probe.serve(lease)
    assert len(calls) == 1
    value = calls[0]
    assert value.host == '127.0.0.1' and value.port == 9446 and value.workers == 1
    assert value.proxy_headers is False and value.forwarded_allow_ips == ''
    assert value.access_log is False and value.ws == 'none' and value.limit_concurrency == 8
    assert value.timeout_graceful_shutdown == 5


def test_caddy_template_is_explicitly_closed():
    value = (FILE.parent / 'Caddyfile.closed.example').read_text()
    for required in ['bind 127.0.0.1', 'auto_https off', 'admin off', 'persist_config off',
            'tls {$KESTREL_QA_CERT_FILE} {$KESTREL_QA_KEY_FILE}', 'reverse_proxy 127.0.0.1:9446',
            'header_up -X-Kestrel-*', 'header_up X-Kestrel-Client-IP {remote_host}']:
        assert required in value


@pytest.mark.skipif(not os.environ.get('KESTREL_CLOSED_QA_CONFIG'), reason='Real target configuration not supplied; OS proof pending')
def test_real_target_identity_file_acls_and_synthetic_dpapi():
    # No monkeypatch, synthetic OS replacement, account creation or ACL repair.
    lease = probe.load_lease(os.environ['KESTREL_CLOSED_QA_CONFIG'])
    evidence = probe.verify_platform(lease)
    assert evidence['real_windows_identity_and_two_file_acls'] is True
    assert evidence['synthetic_same_profile_dpapi_roundtrip'] is True
    assert evidence['operational_acceptance'] is False
    assert 'actual_api_worker_caddy_pg_services' in evidence['pending']
    assert not {'all_required_passed', 'required_checks', 'decision', 'receipt_hash'} & evidence.keys()
