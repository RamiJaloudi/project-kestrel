"""Normal-session contract inventory checks; no legal decisions or provider calls."""
import csv
import hashlib
import http.client
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from kestrel.localenv import read_env
from verify_report_connections import Session, CONTEXT


def main():
    sessions = []
    try:
        password = read_env()['KESTREL_DUMMY_PASSWORD']
        firm = Session('firm.localhost', 'sme01@freshfields.example', password)
        sessions.append(firm)
        status, matters = firm.request('GET', '/api/v1/workflow/matters')
        assert status == 200
        matter = next(m['id'] for m in matters if m['client_number'] == '012345' and m['matter_number'] == '789012')
        payload = {'matter_id': matter, 'length': 50, 'sort': 'file_name', 'source_filters': {'historical': False}}
        status, inventory = firm.request('POST', '/api/v1/tables/inventory/query', payload)
        assert status == 200 and inventory['recordsTotal'] <= 50, 'Narrow this local verification window before proceeding'
        expected = {row['id'] for row in inventory['data'] if row['resource_type'] in {'contract', 'licence'}}
        contract_query = {**payload, 'draw': 7, 'source_filters': {'historical': False, 'contracts_only': True}}
        status, contracts = firm.request('POST', '/api/v1/tables/inventory/query', contract_query)
        assert status == 200 and contracts['draw'] == 7
        assert contracts['recordsTotal'] == contracts['recordsFiltered'] == len(expected)
        assert {row['id'] for row in contracts['data']} == expected
        assert all(row['resource_type'] in {'contract', 'licence'} and 'counterparty' not in row and 'title' not in row for row in contracts['data'])
        status, empty = firm.request('POST', '/api/v1/tables/inventory/query', {**contract_query, 'search': 'absent-contract-72bdb6'})
        assert status == 200 and empty['recordsTotal'] == len(expected) and empty['recordsFiltered'] == 0
        status, _ = firm.request('POST', '/api/v1/tables/inventory/query', {**contract_query, 'source_filters': {'contracts_only': 'true'}})
        assert status == 422
        status, _ = firm.request('POST', '/api/v1/tables/financial/query', contract_query)
        assert status == 422
        exports = {}
        profile_checked = False
        if contracts['data']:
            row = contracts['data'][0]
            status, profile = firm.request('GET', '/api/v1/tables/findings/source-profile/' + row['id'] + '?' + urlencode({'matter_id': matter, 'historical': 'false'}))
            assert status == 200 and isinstance(profile['source_review_available'], bool)
            if profile['source_review_available']:
                assert profile['source']['id'] == row['id'] and profile['source']['resource_type'] in {'contract', 'licence'}
            else:
                assert profile['source'] is None and profile['can_edit'] is False
            profile_checked = True
            for fmt in ['csv', 'xlsx']:
                connection = http.client.HTTPSConnection('localhost', 8443, context=CONTEXT, timeout=30)
                body = {'matter_id': matter, 'ids': [row['id']], 'historical': False, 'format': fmt}
                connection.request('POST', '/api/v1/tables/inventory/export', body=json.dumps(body), headers={'Host': firm.host + ':8443', 'Origin': 'https://' + firm.host + ':8443', 'Cookie': firm.cookie, 'X-CSRF-Token': firm.csrf, 'Content-Type': 'application/json'})
                response = connection.getresponse()
                content = response.read()
                assert response.status == 200 and response.getheader('X-Content-SHA256') == hashlib.sha256(content).hexdigest()
                unavailable = int(response.getheader('X-Export-Unavailable-Count'))
                assert unavailable in {0, 1}
                if fmt == 'csv':
                    rows = list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
                    assert len(rows) == 1 - unavailable
                    if rows:
                        assert rows[0]['id'] == row['id']
                else:
                    from openpyxl import load_workbook
                    book = load_workbook(io.BytesIO(content))
                    assert book.active.max_row == 2 - unavailable and all(cell.data_type != 'f' for cells in book.active for cell in cells)
                    book.close()
                connection.close()
                exports[fmt] = {'included': 1 - unavailable, 'unavailable': unavailable}
        audience_statuses = {}
        for host, user in [('firm.localhost', 'admin01@freshfields.example'), ('bank.localhost', 'bank01@castlegate.example')]:
            session = Session(host, user, password)
            sessions.append(session)
            status, audience_page = session.request('POST', '/api/v1/tables/inventory/query', contract_query)
            audience_statuses[host] = status
            if host == 'firm.localhost':
                assert status == 403
            else:
                # Inventory can return an empty authorized page for an external
                # matter member; this is not a general source-access grant.
                assert status == 403 or status == 200 and audience_page['recordsTotal'] == audience_page['recordsFiltered'] == 0 and audience_page['data'] == []
        report = {'verified': True, 'inventory_total': inventory['recordsTotal'], 'contract_total': len(expected), 'contract_and_licence_only': True, 'search_and_strict_input_checked': True, 'fresh_source_profile_checked': profile_checked, 'selected_inventory_exports': exports, 'audience_statuses': audience_statuses, 'root_denied_bank_sources_withheld': True, 'business_decisions': 0, 'paid_calls': 0}
        (ROOT / '.runtime/contract-tables-live-verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps(report))
    finally:
        for session in sessions:
            status, _ = session.request('POST', '/api/v1/auth/logout', {})
            assert status == 204


if __name__ == '__main__':
    main()
