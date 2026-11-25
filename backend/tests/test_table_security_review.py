"""Independent Gate 4 regressions using only disposable synthetic fixtures."""
import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_auth_policy import env, login
from test_document_workflow import BASE, upload
from test_observability_governance import post

TABLES = '/api/v1/tables'
READERS = '/api/v1/readers'


def confirmed(http, csrf, matter, **changes):
    response = upload(http, csrf, matter, **changes)
    assert response.status_code == 201, response.text
    row = response.json()
    response = post(http, BASE + '/documents/' + row['id'] + '/confirm', csrf, {
        'snapshot_hash': row['snapshot_hash'],
        'rationale': 'Confirm synthetic handling before the independent security regression',
    })
    assert response.status_code == 200, response.text
    return row


def assert_withheld(response, *private_values):
    assert response.status_code in {401, 403, 409}, response.text
    assert 'recordsTotal' not in response.text
    assert 'recordsFiltered' not in response.text
    assert 'content-disposition' not in response.headers
    for value in private_values:
        assert value not in response.text


def test_inventory_selected_exports_and_comparison_stay_in_requested_matter(env):
    """A user cleared for two matters still cannot mix their response scopes."""
    from kestrel.models import MatterAssignment
    from kestrel.services.auth import clock

    http, sessions, ids, _ = env
    with sessions() as db:
        db.add(MatterAssignment(account_id=ids['lawyer'], matter_id=ids['other'], expires_at=clock() + 3600))
        db.commit()
    csrf = login(http).json()['csrf_token']
    own = confirmed(http, csrf, ids['matter'], logical_key='SCOPE-A', file_name='matter-a.txt')
    other = confirmed(http, csrf, ids['other'], logical_key='SCOPE-B', file_name='other-matter-private-name.txt')

    response = post(http, TABLES + '/inventory/query', csrf, {
        'matter_id': ids['matter'], 'search': 'other-matter-private-name',
    })
    assert response.status_code == 200, response.text
    assert response.json()['recordsTotal'] == 1
    assert response.json()['recordsFiltered'] == 0
    assert response.json()['data'] == []
    assert other['id'] not in response.text and other['file_name'] not in response.text

    response = post(http, TABLES + '/inventory/export', csrf, {
        'matter_id': ids['matter'], 'ids': [own['id'], other['id']], 'format': 'csv',
    })
    assert response.status_code == 200, response.text
    assert response.headers['x-export-unavailable-count'] == '1'
    assert [row['id'] for row in csv.DictReader(io.StringIO(response.text))] == [own['id']]
    assert other['id'] not in response.text and other['file_name'] not in response.text

    response = post(http, READERS + '/compare', csrf, {
        'matter_id': ids['matter'], 'targets': [
            {'kind': 'source', 'id': own['id']}, {'kind': 'source', 'id': other['id']},
        ],
    })
    assert response.status_code == 200, response.text
    assert response.json()['panes'][0]['allowed'] is True
    assert response.json()['panes'][1] == {
        'index': 1, 'allowed': False,
        'message': 'Pane unavailable in your current permissions or version state',
    }
    assert other['id'] not in response.text and other['file_name'] not in response.text


@pytest.mark.parametrize('change', ['session', 'account', 'role', 'assignment'])
def test_query_withholds_material_after_identity_authority_changes(env, monkeypatch, change):
    from kestrel.models import Account, MatterAssignment, RoleGrant, ServerSession
    from kestrel.services import data_tables as tables

    http, sessions, ids, _ = env
    csrf = login(http).json()['csrf_token']
    source = confirmed(http, csrf, ids['matter'], file_name='revoked-authority-private-name.txt')
    original = tables.collect

    def collect_then_revoke(db, actor, view, payload):
        records = original(db, actor, view, payload)
        with sessions() as writer:
            if change == 'session':
                writer.scalar(select(ServerSession).where(ServerSession.account_id == ids['lawyer'])).revoked = True
            elif change == 'account':
                writer.get(Account, ids['lawyer']).active = False
            elif change == 'role':
                writer.execute(delete(RoleGrant).where(RoleGrant.account_id == ids['lawyer']))
            else:
                writer.scalar(select(MatterAssignment).where(
                    MatterAssignment.account_id == ids['lawyer'], MatterAssignment.matter_id == ids['matter'],
                )).revoked = True
            writer.commit()
        return records

    monkeypatch.setattr(tables, 'collect', collect_then_revoke)
    response = post(http, TABLES + '/inventory/query', csrf, {'matter_id': ids['matter']})
    assert_withheld(response, source['id'], source['file_name'])
    assert response.status_code == (401 if change in {'session', 'account'} else 403)


@pytest.mark.parametrize('operation', ['query', 'csv', 'xlsx'])
def test_new_restrictive_content_assertion_withholds_prepared_table_or_file(env, monkeypatch, operation):
    """A real label workflow can tighten the original while its metadata is scanned."""
    from kestrel.models import CleanTeamMembership
    from kestrel.services import data_tables as tables
    from kestrel.services.auth import clock

    http, sessions, ids, app = env
    csrf = login(http).json()['csrf_token']
    source = confirmed(http, csrf, ids['matter'], file_name='new-label-private-name.txt')
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['sme'], matter_id=ids['matter'], scope='pricing',
                                   approved_by=ids['root'], expires_at=clock() + 3600))
        db.commit()
    original = tables.collect if operation == 'query' else tables.selected

    def prepare_then_restrict(db, actor, view, payload):
        records = original(db, actor, view, payload)
        with TestClient(app, base_url='https://firm.localhost') as reviewer:
            token = login(reviewer, 'sme').json()['csrf_token']
            response = post(reviewer, '/api/v1/content-labels/sources/' + source['id'], token, {
                'expected_revision': 0, 'request_key': 'independent-tighten-001',
                'labels': ['competitively_sensitive'], 'clean_team_scope': 'pricing',
                'rationale': 'New source restriction must invalidate the in-flight synthetic table response',
            })
            assert response.status_code == 201, response.text
        return records

    monkeypatch.setattr(tables, 'collect' if operation == 'query' else 'selected', prepare_then_restrict)
    if operation == 'query':
        response = post(http, TABLES + '/inventory/query', csrf, {'matter_id': ids['matter']})
    else:
        response = post(http, TABLES + '/inventory/export', csrf, {
            'matter_id': ids['matter'], 'ids': [source['id']], 'format': operation,
        })
    assert_withheld(response, source['id'], source['file_name'])
    assert response.status_code == 409


def test_revoked_candidate_cursor_is_opaque_and_does_not_break_other_permitted_panes(env):
    from kestrel.models import CleanTeamMembership
    from kestrel.services.auth import clock

    http, sessions, ids, _ = env
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'], matter_id=ids['matter'], scope='pricing',
                                   approved_by=ids['sme'], expires_at=clock() + 3600))
        db.commit()
    csrf = login(http).json()['csrf_token']
    ordinary = confirmed(http, csrf, ids['matter'], logical_key='CURSOR-ORDINARY')
    secret = confirmed(http, csrf, ids['matter'], logical_key='CURSOR-SECRET',
                       file_name='cursor-private-name.txt', classification='clean_team', clean_team_scope='pricing')
    with sessions() as db:
        db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id == ids['lawyer'])).revoked = True
        db.commit()
    response = http.get(READERS + '/candidates', params={
        'matter_id': ids['matter'], 'kind': 'source', 'after': secret['id'],
    })
    assert response.status_code == 404
    assert secret['id'] not in response.text and secret['file_name'] not in response.text
    response = http.get(READERS + '/candidates', params={'matter_id': ids['matter'], 'kind': 'source'})
    assert response.status_code == 200, response.text
    assert [r['id'] for r in response.json()['rows']] == [ordinary['id']]
    assert 'recordsTotal' not in response.text and 'authorized_count' not in response.text


def test_comparison_bounds_use_unicode_characters_and_hide_invalid_location(env, monkeypatch):
    import test_document_workflow as documents

    text = '😀Synthetic evidence. Two Unicode code points precede n: 😀n.'
    monkeypatch.setattr(documents, 'TEXT', text)
    http, _, ids, _ = env
    csrf = login(http).json()['csrf_token']
    source = confirmed(http, csrf, ids['matter'])
    response = post(http, READERS + '/compare', csrf, {
        'matter_id': ids['matter'], 'targets': [
            {'kind': 'source', 'id': source['id'], 'unit': 1, 'start': 1, 'end': 2},
            {'kind': 'source', 'id': source['id'], 'unit': 1, 'start': 1, 'end': len(text) + 1},
        ],
    })
    assert response.status_code == 200, response.text
    permitted, unavailable = response.json()['panes']
    assert permitted['target']['start'] == 1 and permitted['target']['end'] == 2
    assert permitted['citation_anchors'][0]['end'] == len(text)
    assert set(unavailable) == {'index', 'allowed', 'message'} and unavailable['allowed'] is False


@pytest.mark.parametrize('change', ['approver_role', 'approver_assignment', 'bank_gate'])
def test_external_financial_counts_withheld_after_approval_authority_or_gate_changes(env, monkeypatch, change):
    """The bank's unchanged identity cannot preserve a now-invalid approval chain."""
    import test_disclosures as disclosures
    import test_document_workflow as documents
    from test_financial_workflow import TEXT, F, decision, payload
    from kestrel.models import FinancialAccessGate, MatterAssignment, Role, RoleGrant
    from kestrel.services import data_tables as tables
    from kestrel.services.auth import clock

    content = documents.TEXT + ' ' + TEXT
    monkeypatch.setattr(documents, 'TEXT', content)
    monkeypatch.setattr(disclosures, 'TEXT', content)
    http, sessions, ids, app = env
    source, _, artifact, _ = disclosures.prepared(env)
    token = login(http, 'sme').json()['csrf_token']
    response = post(http, disclosures.D + '/artifacts/' + artifact['id'] + '/decisions', token, {
        'operation': 'legal_approve', 'bundle_hash': artifact['bundle_hash'],
        'rationale': 'Independent approval of a synthetic transcript for bank-boundary tests',
    })
    assert response.status_code == 200, response.text
    token = login(http).json()['csrf_token']
    text = http.get(disclosures.D + '/artifacts/' + artifact['id'] + '/reader').json()['units'][0]['text']
    response = post(http, F + '/facts', token, payload(artifact['id'], text, 'derivative'))
    assert response.status_code == 201, response.text
    fact = response.json()
    token = login(http, 'sme').json()['csrf_token']
    assert decision(http, token, fact, 'verify').status_code == 200
    assert decision(http, token, fact, 'release').status_code == 200
    token = login(http, 'root').json()['csrf_token']
    response = post(http, F + '/bank-gate?matter_id=' + ids['matter'], token, {
        'expected_revision': 0, 'enabled': True,
        'rationale': 'Enable the synthetic bank feature after individual approval',
    })
    assert response.status_code == 200, response.text
    from test_financial_workflow import enable_org
    enable_org(http, token)
    original = tables.collect

    def collect_then_revoke(db, actor, view, table_payload):
        records = original(db, actor, view, table_payload)
        assert len(records) == 1
        with sessions() as writer:
            if change == 'approver_role':
                role = writer.scalar(select(Role.id).where(Role.name == 'legal_sme'))
                writer.execute(delete(RoleGrant).where(RoleGrant.account_id == ids['sme'], RoleGrant.role_id == role))
            elif change == 'approver_assignment':
                writer.scalar(select(MatterAssignment).where(
                    MatterAssignment.account_id == ids['sme'], MatterAssignment.matter_id == ids['matter'],
                )).revoked = True
            else:
                writer.add(FinancialAccessGate(matter_id=ids['matter'], revision=2, enabled=False,
                           actor_id=ids['root'], rationale='Disable synthetic bank access during preparation', occurred_at=clock()))
            writer.commit()
        return records

    monkeypatch.setattr(tables, 'collect', collect_then_revoke)
    with TestClient(app, base_url='https://bank.localhost') as bank:
        token = login(bank, 'bank', origin='https://bank.localhost').json()['csrf_token']
        response = bank.post(TABLES + '/financial/query', json={'matter_id': ids['matter']}, headers={
            'origin': 'https://bank.localhost', 'x-csrf-token': token,
        })
        assert_withheld(response, source['id'], artifact['id'], fact['id'], fact['amount_text'])


@pytest.mark.parametrize('endpoint', ['compare', 'candidates'])
def test_reader_responses_withhold_prepared_metadata_when_wall_changes(env, monkeypatch, endpoint):
    """The response itself must withhold titles/coordinates after in-flight revocation."""
    from kestrel.models import EthicalWall
    from kestrel.services import readers

    http, sessions, ids, _ = env
    csrf = login(http).json()['csrf_token']
    first = confirmed(http, csrf, ids['matter'], logical_key='READER-WALL-A', file_name='reader-private-a.txt')
    second = confirmed(http, csrf, ids['matter'], logical_key='READER-WALL-B', file_name='reader-private-b.txt')
    original = readers.resource
    changed = False

    def resource_then_wall(*args, **kwargs):
        nonlocal changed
        result = original(*args, **kwargs)
        if not changed:
            changed = True
            with sessions() as writer:
                writer.add(EthicalWall(account_id=ids['lawyer'], matter_id=ids['matter'], active=True))
                writer.commit()
        return result

    monkeypatch.setattr(readers, 'resource', resource_then_wall)
    if endpoint == 'compare':
        response = post(http, READERS + '/compare', csrf, {
            'matter_id': ids['matter'], 'targets': [
                {'kind': 'source', 'id': first['id']}, {'kind': 'source', 'id': second['id']},
            ],
        })
    else:
        response = http.get(READERS + '/candidates', params={'matter_id': ids['matter'], 'kind': 'source'})
    assert_withheld(response, first['id'], second['id'], first['file_name'], second['file_name'])
    assert 'citation_anchors' not in response.text
