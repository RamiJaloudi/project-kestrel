"""Actual official parser, only in offline adaptation mode; no listener or keys."""
import importlib.util
import os
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
BINARY=ROOT/'.runtime/tools/caddy-v2.11.9/caddy.exe'
pytestmark=pytest.mark.skipif(os.name!='nt' or not BINARY.is_file(),reason='Separately verified Windows Caddy offline tool required')


def checker():
    spec=importlib.util.spec_from_file_location('kestrel_proxy_review',ROOT/'scripts/check_proxy_template.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def test_actual_proxy_template_adapts_without_real_token(monkeypatch):
    module=checker();monkeypatch.setenv('KESTREL_PROXY_TOKEN','NEVER-USE-THIS-AMBIENT-TEST-CANARY')
    receipt=module.review(BINARY)
    assert receipt['adapted'] and receipt['admin_disabled'] and receipt['private_upstream']
    assert len(receipt['hosts'])==5
    assert 'NEVER-USE-THIS-AMBIENT-TEST-CANARY' not in str(receipt)
    assert 'no listener' in receipt['scope']


def test_unverified_binary_is_rejected_before_any_execution(tmp_path):
    module=checker();bad=tmp_path/'untrusted.exe';bad.write_bytes(b'nonexecutable-test-canary')
    with pytest.raises(ValueError,match='Verified official'):module.review(bad)


@pytest.mark.parametrize('old,new',[
    ('admin off','admin localhost:2019'),
    ('reverse_proxy 127.0.0.1:8000','reverse_proxy 127.0.0.1:9000'),
    ('header_up -X-Kestrel-*','header_up -X-Unrelated-*'),
    ('castlegate.portal.ramijaloudi.com','lookalike.example'),
])
def test_offline_checker_refuses_boundary_drift(tmp_path,old,new):
    module=checker();target=tmp_path/'deployment';target.mkdir()
    original=(ROOT/'deployment/Caddyfile.public.example').read_text(encoding='utf-8')
    assert old in original
    (target/'Caddyfile.public.example').write_text(original.replace(old,new),encoding='utf-8')
    module.ROOT=tmp_path
    with pytest.raises(ValueError):module.review(BINARY)
