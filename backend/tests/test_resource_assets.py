"""Resource library confidentiality, retained asset integrity and dictionary provenance."""
import csv
import hashlib
import io
import json
from decimal import Decimal
from fastapi.testclient import TestClient
from test_auth_policy import env, login
from kestrel.api import resource_assets as assets
from kestrel.models import Account, Base

URL = '/api/v1/resources/assets'


def test_all_downloads_require_current_sign_in(env):
    http, sessions, ids, _ = env
    assert http.get(URL).status_code == 401
    assert http.get(URL+'/implemented-schema-fields/download').status_code == 401
    assert login(http).status_code == 200
    entries = http.get(URL).json()
    assert {'Guides','Diagrams','Sample ledgers','Sample reports','Forms and trackers','API and schema'} <= {e['category'] for e in entries}
    for entry in entries:
        response = http.get(entry['download_href'])
        assert response.status_code == 200, entry['id']
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['content-disposition'].startswith('attachment;')
        assert hashlib.sha256(response.content).hexdigest() == entry['sha256']
    with sessions() as db:
        db.get(Account, ids['lawyer']).active = False; db.commit()
    assert http.get(entries[0]['download_href']).status_code == 401


def test_external_audiences_get_their_own_synthetic_report_only(env):
    _, _, _, app = env
    for name, host, own, other in [('client','client','halden','castlegate'),('bank','bank','castlegate','halden')]:
        with TestClient(app, base_url=f'https://{host}.localhost') as http:
            assert login(http, name, origin=f'https://{host}.localhost').status_code == 200
            entries = http.get(URL).json(); ids = {item['id'] for item in entries}
            assert own+'-due-diligence-sample' in ids if own=='halden' else 'castlegate-commercial-report-sample' in ids
            assert 'internal-due-diligence-sample' not in ids
            assert 'implemented-schema-fields' not in ids
            assert 'approval-decision-ledger' not in ids
            forbidden = ['internal-due-diligence-sample','implemented-schema-fields',
                         'halden-due-diligence-sample' if other=='halden' else 'castlegate-commercial-report-sample']
            for asset_id in forbidden:
                assert http.get(URL+'/'+asset_id+'/download').status_code == 404


def test_unknown_paths_and_changed_assets_are_never_served(env, tmp_path, monkeypatch):
    http, _, _, _ = env; login(http)
    for asset_id in ['missing','catalog.json','.env','credentials','..%2F..%2F.env']:
        assert http.get(URL+'/'+asset_id+'/download').status_code == 404
    original = assets.catalogue()[0]
    (tmp_path/'catalog.json').write_text(json.dumps({'assets':[original]}), encoding='utf-8')
    (tmp_path/original['filename']).write_bytes(b'Tampered asset')
    monkeypatch.setattr(assets, 'LIBRARY', tmp_path)
    response = http.get(URL+'/'+original['id']+'/download')
    assert response.status_code == 503 and b'Tampered asset' not in response.content


def test_schema_provenance_and_sample_ledger_balance():
    def rows(name):
        with (assets.LIBRARY/name).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    implemented = rows('Implemented_Schema_Fields.csv')
    assert len(implemented) == sum(len(table.columns) for table in Base.metadata.tables.values())
    assert {row['schema_status'] for row in implemented} == {'IMPLEMENTED MODEL SNAPSHOT'}
    proposed = rows('Proposed_Schema_Fields.csv')
    assert len(proposed)==809 and all('PROPOSED' in row['schema_status'] for row in proposed)
    ledger = rows('Financial_Transaction_Ledger.csv')
    assert {row['currency'] for row in ledger} == {'EUR'}
    assert all(row['example_status']=='SYNTHETIC' for row in ledger)
    for entry_id in {row['entry_id'] for row in ledger}:
        entry = [row for row in ledger if row['entry_id']==entry_id]
        assert sum(Decimal(row['debit']) for row in entry) == sum(Decimal(row['credit']) for row in entry)
    definitions = rows('Ledger_Field_Definitions.csv')
    for path in assets.LIBRARY.glob('*_Ledger.csv'):
        data = rows(path.name)
        assert set(data[0]) == {r['field'] for r in definitions if r['file']==path.name}


def test_api_explorer_points_to_current_portal_schema_downloads(env):
    http, _, _, _ = env
    response = http.get('/docs')
    assert '/portal?view=Resources&amp;resourceCategory=schema' in response.text
