"""Static draft tests only; no Windows service, credentials or network calls."""
import importlib.util
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import pytest

FILE = Path(__file__).resolve().parents[1] / 'prepare_service_plan.py'
spec = importlib.util.spec_from_file_location('kestrel_service_static_plan', FILE)
plan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plan
spec.loader.exec_module(plan)


@pytest.fixture
def value():
    return json.loads((FILE.parent / 'service-plan.example.json').read_text())


def test_exact_review_only_artifacts_and_fixed_commands(value):
    outputs = plan.render(value)
    assert set(outputs) == {'KestrelPublicApi.xml.review-only', 'KestrelPublicProxy.xml.review-only', 'service-plan.json'}
    api = ET.fromstring(outputs['KestrelPublicApi.xml.review-only'])
    assert api.findtext('executable') == value['python_exe']
    assert api.findtext('arguments') == '-m kestrel.public_service'
    assert {node.attrib['name']: node.attrib['value'] for node in api.findall('env')} == {
        'PYTHONPATH': 'E:\\Kestrel\\app\\backend', 'KESTREL_ENV': 'PUBLIC_DEMO',
        'KESTREL_PUBLIC_CONFIG': value['public_config_file']}
    proxy = ET.fromstring(outputs['KestrelPublicProxy.xml.review-only'])
    assert proxy.findtext('executable') == value['caddy_exe']
    assert proxy.findtext('arguments') == 'run --config "E:\\Kestrel\\owner\\Caddyfile.public" --adapter caddyfile'
    assert not proxy.findall('env')


def test_manual_no_recovery_append_and_no_account_or_secret_xml(value):
    for name, data in plan.render(value).items():
        if not name.endswith('.review-only'):
            continue
        xml = ET.fromstring(data)
        assert xml.findtext('startmode') == 'Manual'
        assert xml.find('onfailure').attrib == {'action': 'none'}
        assert xml.find('log').attrib == {'mode': 'append'}
        assert xml.findtext('stoptimeout') == '15sec'
        assert not xml.findall('serviceaccount')
        assert not xml.findall('download')
        assert not xml.findall('delayedAutoStart')
        assert not xml.findall('envFile')
        assert 'password' not in data.decode().lower()
        assert 'proxy_token' not in data.decode().lower()


def test_worker_and_all_installs_remain_explicitly_blocked(value):
    report = json.loads(plan.render(value)['service-plan.json'])
    assert report['operational_acceptance'] is False
    assert report['wrapper_candidate']['target_binary_verified'] is False
    assert report['wrapper_candidate']['sha256'] == '4ebd9dc3e817f80b2bd8c18f5bfe0d550241c1d08b57bd9694777a6e56a7b24f'
    assert len(report['services']) == 3
    for service in report['services']:
        assert service['start_mode'] == 'Manual' and service['automatic_recovery'] == 'none'
        assert service['log_mode'] == 'append' and service['installable'] is False
        assert service['manual_start_requires_valid_public_gate'] is True
    worker = next(row for row in report['services'] if row['id'] == 'KestrelPublicWorker')
    assert worker['draft'] is None
    assert 'reviewed_PUBLIC_worker_entrypoint_missing' in worker['blockers']


@pytest.mark.parametrize('extra', ['password', 'database_url', 'proxy_token', 'arguments', 'startup', 'worker_executable'])
def test_unknown_or_secret_inputs_rejected(value, extra):
    with pytest.raises(ValueError):
        plan.render({**value, extra: 'unaccepted'})


@pytest.mark.parametrize('path', ['relative\\python.exe', '\\\\host\\share\\python.exe',
    'E:\\Kestrel\\..\\python.exe', 'E:\\Kestrel\\%APPDATA%\\python.exe',
    'E:\\Kestrel\\bad"name\\python.exe', 'E:\\Kestrel\\python.exe:stream',
    'E:\\Kestrel\\bad\nname\\python.exe', 'E:\\'])
def test_unsafe_paths_rejected(value, path):
    with pytest.raises(ValueError):
        plan.render({**value, 'python_exe': path})


@pytest.mark.parametrize('key', ['public_config_file', 'public_caddyfile', 'service_root'])
def test_owner_service_files_cannot_be_in_release(value, key):
    with pytest.raises(ValueError):
        plan.render({**value, key: 'e:\\kestrel\\app\\unsafe'})


@pytest.mark.parametrize('account', ['LocalSystem', 'NT AUTHORITY\\SYSTEM', 'HOST\\Administrator',
    'HOST\\LocalSystem', 'HOST\\user;Write-Output bad', 'HOST\\user\n'])
def test_builtin_or_unsafe_accounts_rejected(value, account):
    with pytest.raises(ValueError):
        plan.render({**value, 'app_account': account})


def test_distinct_sid_and_account_requirements(value):
    for changed in [{'app_sid': value['owner_sid']}, {'proxy_sid': value['app_sid']},
            {'app_sid': 'S-1-5-18'}, {'proxy_account': value['app_account']}]:
        with pytest.raises(ValueError):
            plan.render({**value, **changed})


def test_duplicate_json_fields_rejected():
    with pytest.raises(ValueError):
        json.loads('{"schema":1,"schema":2}', object_pairs_hook=plan.distinct_json)


def test_new_directory_only_no_overwrite(value, tmp_path):
    target = tmp_path / 'review-only'
    plan.write_new(value, target)
    original = {item.name: item.read_bytes() for item in target.iterdir()}
    with pytest.raises(FileExistsError):
        plan.write_new(value, target)
    assert original == {item.name: item.read_bytes() for item in target.iterdir()}
