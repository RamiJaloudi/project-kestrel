"""Read-only scoped audit paging and complete searched ZIP-manifest checks."""
import csv
import hashlib
import http.client
import io
import json
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from kestrel.localenv import read_env
from verify_report_connections import Session, CONTEXT

FIELDS = {'id', 'occurred_at', 'actor_id', 'category', 'matter_id', 'object_id', 'clean_team_scope', 'action', 'outcome', 'correlation_id'}


def main():
    sessions = []
    try:
        password = read_env()['KESTREL_DUMMY_PASSWORD']
        root = Session('admin.localhost', 'admin01@freshfields.example', password)
        sessions.append(root)
        status, identity = root.request('GET', '/api/v1/auth/me')
        assert status == 200
        end = int(time.time()) - 2
        scope = {'category': 'administrative', 'from_time': end - 3600, 'to_time': end}
        payload = {'draw': 3, 'length': 1, 'sort': 'occurred_at', 'direction': 'desc', 'audit_filters': scope}
        status, baseline = root.request('POST', '/api/v1/audit/query', payload)
        assert status == 200 and 0 <= baseline['recordsTotal'] <= 1000
        filtered_query = {**payload, 'search': 'account.directory', 'column_filters': {'outcome': 'allowed'}}
        status, filtered = root.request('POST', '/api/v1/audit/query', filtered_query)
        assert status == 200 and filtered['draw'] == 3 and filtered['recordsTotal'] == baseline['recordsTotal']
        assert filtered['recordsFiltered'] >= 2, 'The verifier needs at least two recent directory-read audit events'
        rows = []
        for offset in range(0, filtered['recordsFiltered'], 50):
            status, page = root.request('POST', '/api/v1/audit/query', {**filtered_query, 'start': offset, 'length': 50})
            assert status == 200 and page['recordsTotal'] == baseline['recordsTotal'] and page['recordsFiltered'] == filtered['recordsFiltered']
            rows.extend(page['data'])
        ids = [row['id'] for row in rows]
        assert len(ids) == len(set(ids)) == filtered['recordsFiltered']
        assert rows == sorted(rows, key=lambda row: (-row['occurred_at'], row['id']))
        assert all(set(row) == FIELDS and 'account.directory' in row['action'] and 'allowed' in row['outcome'] for row in rows)
        status, second = root.request('POST', '/api/v1/audit/query', {**filtered_query, 'start': 1})
        assert status == 200 and second['data'][0]['id'] == ids[1]
        formats = {}
        for fmt in ['jsonl', 'csv', 'html', 'pdf']:
            connection = http.client.HTTPSConnection('localhost', 8443, context=CONTEXT, timeout=60)
            # An offset and one-row page must not restrict the audit package.
            body = {**filtered_query, 'start': 1, 'length': 1, 'format': fmt}
            connection.request('POST', '/api/v1/audit/export-query', body=json.dumps(body), headers={'Host': root.host + ':8443', 'Origin': 'https://' + root.host + ':8443', 'Cookie': root.cookie, 'X-CSRF-Token': root.csrf, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            content = response.read()
            assert response.status == 200 and response.getheader('Content-Type', '').startswith('application/zip')
            connection.close()
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                assert set(archive.namelist()) == {'events.' + fmt, 'manifest.json'}
                data = archive.read('events.' + fmt)
                manifest = json.loads(archive.read('manifest.json'))
            assert manifest['event_ids'] == ids and manifest['count'] == len(ids) and manifest['exported_by'] == identity['id']
            assert manifest['sha256'] == hashlib.sha256(data).hexdigest() and manifest['immutable_storage'] is False
            descriptor = manifest['filters']
            assert descriptor['selection'] == 'all_filtered' and descriptor['search'] == filtered_query['search'] and descriptor['column_filters'] == filtered_query['column_filters']
            assert descriptor['sort'] == payload['sort'] and descriptor['direction'] == payload['direction']
            assert descriptor['audit_filters']['from_time'] == scope['from_time'] and descriptor['audit_filters']['to_time'] == scope['to_time']
            assert 'start' not in descriptor and 'length' not in descriptor
            if fmt == 'jsonl':
                records = [json.loads(line) for line in data.decode('utf8').splitlines()]
                assert records == rows
            elif fmt == 'csv':
                records = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
                assert [row['id'] for row in records] == ids
            elif fmt == 'html':
                assert b'<!doctype html>' in data and all(event_id.encode() in data for event_id in ids)
            else:
                assert data.startswith(b'%PDF-')
            formats[fmt] = {'count': manifest['count'], 'hash_verified': True}
        status, _ = root.request('POST', '/api/v1/audit/query', {**payload, 'audit_filters': {**scope, 'from_time': end + 1}})
        assert status == 422
        status, _ = root.request('POST', '/api/v1/audit/query', {**payload, 'source_filters': {}})
        assert status == 422
        for host, user in [('client.localhost', 'client01@halden.example'), ('bank.localhost', 'bank01@castlegate.example')]:
            session = Session(host, user, password)
            sessions.append(session)
            status, who = session.request('GET', '/api/v1/auth/me')
            assert status == 200
            status, own = session.request('POST', '/api/v1/audit/query', payload)
            assert status == 200 and all(row['actor_id'] == who['id'] for row in own['data'])
        status, profile = root.request('GET', '/api/v1/auth/profile')
        assert status == 200
        no_clean_override = None
        if not profile['clean_team_scopes']:
            status, _ = root.request('POST', '/api/v1/audit/query', {**payload, 'audit_filters': {**scope, 'category': 'clean_team'}})
            assert status == 403
            no_clean_override = True
        report = {'verified': True, 'permitted_window_total': baseline['recordsTotal'], 'searched_count': len(ids), 'stable_paging': True, 'all_searched_export_formats': formats, 'manifest_matches_grid_across_pages': True, 'external_own_activity_only': True, 'root_without_named_scope_denied': no_clean_override, 'identity_or_legal_writes': 0, 'paid_calls': 0}
        (ROOT / '.runtime/audit-tables-live-verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps(report))
    finally:
        for session in sessions:
            status, _ = session.request('POST', '/api/v1/auth/logout', {})
            assert status == 204


if __name__ == '__main__':
    main()
