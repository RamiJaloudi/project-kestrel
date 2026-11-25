"""Read-only administrator directory checks through ordinary local sessions."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from kestrel.localenv import read_env
from verify_report_connections import Session


def main():
    sessions = []
    try:
        password = read_env()['KESTREL_DUMMY_PASSWORD']
        root = Session('admin.localhost', 'admin01@freshfields.example', password)
        sessions.append(root)
        status, directory = root.request('GET', '/api/v1/admin/accounts')
        assert status == 200 and 0 < len(directory) <= 50, 'Narrow the local verifier window before using a larger directory'
        fields = {'id', 'upn', 'display_name', 'employee_id', 'organization', 'roles', 'active', 'revision'}
        assert all(set(row) == fields and isinstance(row['employee_id'], str) for row in directory)
        payload = {'draw': 9, 'length': 50, 'sort': 'display_name', 'direction': 'asc'}
        status, page = root.request('POST', '/api/v1/admin/accounts/query', payload)
        assert status == 200 and page['draw'] == 9 and page['recordsTotal'] == page['recordsFiltered'] == len(directory)
        assert {row['id'] for row in page['data']} == {row['id'] for row in directory}
        assert all(set(row) == fields for row in page['data'])
        status, first = root.request('POST', '/api/v1/admin/accounts/query', {**payload, 'length': 1})
        status2, second = root.request('POST', '/api/v1/admin/accounts/query', {**payload, 'length': 1, 'start': 1})
        assert status == status2 == 200 and first['data'][0]['id'] == page['data'][0]['id'] and second['data'][0]['id'] == page['data'][1]['id']
        counts = {}
        for employer in ['firm', 'halden', 'castlegate']:
            expected = {row['id'] for row in directory if row['organization'] == employer}
            status, filtered = root.request('POST', '/api/v1/admin/accounts/query', {**payload, 'account_filters': {'organization': employer}})
            assert status == 200 and filtered['recordsTotal'] == filtered['recordsFiltered'] == len(expected)
            assert {row['id'] for row in filtered['data']} == expected
            counts[employer] = len(expected)
        status, empty = root.request('POST', '/api/v1/admin/accounts/query', {**payload, 'search': 'absent-directory-5b8a13'})
        assert status == 200 and empty['recordsTotal'] == len(directory) and empty['recordsFiltered'] == 0 and empty['data'] == []
        row = first['data'][0]
        status, detail = root.request('GET', '/api/v1/admin/accounts/' + row['id'] + '?revision=' + str(row['revision']))
        assert status == 200 and detail == row
        status, _ = root.request('GET', '/api/v1/admin/accounts/' + row['id'] + '?revision=' + str(row['revision'] + 1))
        assert status == 409
        for bad in [{**payload, 'matter_id': 'not-a-directory-scope'}, {**payload, 'length': 51}, {**payload, 'sort': 'password_hash'}, {**payload, 'account_filters': {'active': 'true'}}]:
            status, _ = root.request('POST', '/api/v1/admin/accounts/query', bad)
            assert status == 422
        for host, user in [('firm.localhost', 'sme01@freshfields.example'), ('client.localhost', 'client01@halden.example'), ('bank.localhost', 'bank01@castlegate.example')]:
            session = Session(host, user, password)
            sessions.append(session)
            status, denied = session.request('POST', '/api/v1/admin/accounts/query', payload)
            assert status == 403 and 'recordsTotal' not in denied and 'data' not in denied
            status, denied = session.request('GET', '/api/v1/admin/accounts/' + row['id'] + '?revision=' + str(row['revision']))
            assert status == 403 and 'upn' not in denied
        report = {'verified': True, 'directory_total': len(directory), 'employer_counts': counts, 'exact_metadata_contract': True, 'stable_pages': True, 'empty_search_and_strict_inputs': True, 'pinned_detail_and_stale_conflict': True, 'sme_client_bank_denied': True, 'identity_writes': 0, 'paid_calls': 0}
        (ROOT / '.runtime/account-tables-live-verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps(report))
    finally:
        for session in sessions:
            status, _ = session.request('POST', '/api/v1/auth/logout', {})
            assert status == 204


if __name__ == '__main__':
    main()
