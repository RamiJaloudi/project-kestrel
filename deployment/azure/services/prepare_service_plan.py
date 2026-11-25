"""Static review drafts only. No installs, credentials, network or service calls."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
from xml.etree import ElementTree as ET

SCHEMA = 'kestrel-windows-services-plan-1'
FIELDS = {'schema', 'release_root', 'python_exe', 'caddy_exe', 'public_config_file',
          'public_caddyfile', 'service_root', 'log_root', 'owner_sid',
          'app_account', 'app_sid', 'proxy_account', 'proxy_sid'}
PATHS = ('release_root', 'python_exe', 'caddy_exe', 'public_config_file',
         'public_caddyfile', 'service_root', 'log_root')
WRAPPER = {'version': 'v2.14.0', 'asset': 'WinSW-x64.exe', 'bytes': 18845338,
           'sha256': '4ebd9dc3e817f80b2bd8c18f5bfe0d550241c1d08b57bd9694777a6e56a7b24f',
           'source': 'https://github.com/winsw/winsw/releases/tag/v2.14.0',
           'target_binary_verified': False}


def distinct_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate input field')
        value[key] = item
    return value


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA:
        raise ValueError('Exact nonsecret services-plan schema required')
    for key in PATHS:
        raw = value[key]
        if not isinstance(raw, str) or re.search(r'[\x00-\x1f"%<>|*?]', raw):
            raise ValueError('Literal local target path required')
        path = PureWindowsPath(raw)
        if not re.fullmatch(r'[A-Za-z]:', path.drive) or not path.is_absolute() or '..' in path.parts or len(path.parts) < 3:
            raise ValueError('Absolute non-root drive path required; no UNC or traversal')
        # Reject alternate data streams and malformed drive components.
        if any(':' in part for part in path.parts[1:]):
            raise ValueError('Alternate streams are not target files')
    release = PureWindowsPath(value['release_root'])
    for key in ('public_config_file', 'public_caddyfile', 'service_root'):
        if PureWindowsPath(value[key]).is_relative_to(release):
            raise ValueError('Owner/service files must be outside the release')
    if PureWindowsPath(value['python_exe']).name.lower() != 'python.exe' or PureWindowsPath(value['caddy_exe']).name.lower() != 'caddy.exe':
        raise ValueError('Explicit reviewed executable names required')
    for key in ('owner_sid', 'app_sid', 'proxy_sid'):
        if not isinstance(value[key], str) or not re.fullmatch(r'S-1-5-21-(?:[0-9]+-)*[0-9]+', value[key]):
            raise ValueError('Explicit non-built-in account SID required')
    if len({value[key] for key in ('owner_sid', 'app_sid', 'proxy_sid')}) != 3:
        raise ValueError('Distinct owner/app/proxy SIDs required')
    for key in ('app_account', 'proxy_account'):
        account = value[key]
        if not isinstance(account, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\\[A-Za-z0-9_.-]+', account):
            raise ValueError('Explicit machine/domain and user required')
        domain, user = account.lower().split('\\')
        if domain in {'nt authority', 'nt service', 'builtin'} or user in {'localsystem', 'localservice', 'networkservice', 'system', 'administrator'}:
            raise ValueError('Built-in/administrator service identity forbidden')
    if value['app_account'].lower() == value['proxy_account'].lower():
        raise ValueError('Distinct app/proxy account names required')
    return value


def xml_draft(value, service, executable, arguments, environment):
    root = ET.Element('service')
    for key, text in [('id', service), ('name', service),
        ('description', 'REVIEW ONLY: blocked pending target prerequisites and valid PUBLIC approval'),
        ('executable', executable), ('arguments', arguments),
        ('workingdirectory', value['release_root']), ('startmode', 'Manual'),
        ('logpath', str(PureWindowsPath(value['log_root']) / service)), ('stoptimeout', '15sec')]:
        ET.SubElement(root, key).text = text
    ET.SubElement(root, 'onfailure', {'action': 'none'})
    ET.SubElement(root, 'log', {'mode': 'append'})
    for key, text in environment.items():
        ET.SubElement(root, 'env', {'name': key, 'value': text})
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


def render(value):
    value = validate(value)
    api = 'KestrelPublicApi'
    proxy = 'KestrelPublicProxy'
    drafts = {
        api + '.xml.review-only': xml_draft(value, api, value['python_exe'], '-m kestrel.public_service',
            {'PYTHONPATH': str(PureWindowsPath(value['release_root']) / 'backend'),
             'KESTREL_ENV': 'PUBLIC_DEMO', 'KESTREL_PUBLIC_CONFIG': value['public_config_file']}),
        proxy + '.xml.review-only': xml_draft(value, proxy, value['caddy_exe'],
            'run --config "' + value['public_caddyfile'] + '" --adapter caddyfile', {}),
    }
    common = {'start_mode': 'Manual', 'automatic_recovery': 'none', 'log_mode': 'append',
              'installable': False, 'manual_start_requires_valid_public_gate': True}
    plan = {'schema': SCHEMA, 'purpose': 'static-target-review-only', 'wrapper_candidate': WRAPPER,
        'operational_acceptance': False, 'source_input_sha256': hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'services': [
            {**common, 'id': api, 'account': value['app_account'], 'expected_sid': value['app_sid'],
             'blockers': ['real_SID_and_logon_right', 'owner_ancestor_ACLs', 'profile_and_private_PostgreSQL', 'actual_PUBLIC_receipt_and_approval', 'SCM_target_test']},
            {**common, 'id': 'KestrelPublicWorker', 'account': value['app_account'], 'expected_sid': value['app_sid'],
             'draft': None, 'blockers': ['reviewed_PUBLIC_worker_entrypoint_missing', 'actual_PUBLIC_gate', 'lease_shutdown_and_authority_tests', 'SCM_target_test']},
            {**common, 'id': proxy, 'account': value['proxy_account'], 'expected_sid': value['proxy_sid'],
             'blockers': ['reviewed_private_process_token_launcher_missing', 'real_SID_and_logon_right', 'owner_ancestor_ACLs', 'actual_PUBLIC_gate', 'TLS_and_SCM_target_test']}],
        'drafts': [{'file': name, 'sha256': hashlib.sha256(data).hexdigest()} for name, data in drafts.items()],
        'rollback': 'Stop only after authority; retain registrations, files and logs. No automatic uninstall or account deletion.'}
    drafts['service-plan.json'] = (json.dumps(plan, indent=2) + '\n').encode()
    return drafts


def write_new(value, output):
    drafts = render(value)
    output = Path(output)
    output.mkdir(parents=False, exist_ok=False)
    for name, data in drafts.items():
        with (output / name).open('xb') as stream:
            stream.write(data)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    path = Path(args.config)
    if path.stat().st_size > 32768:
        raise ValueError('Input exceeds bound')
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=distinct_json)
    output = write_new(value, args.out)
    print(json.dumps({'review_directory': str(output), 'files': 3, 'installed': False,
                      'operational_acceptance': False, 'worker_blocked': True}))


if __name__ == '__main__':
    main()
