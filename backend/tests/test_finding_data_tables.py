"""Independent finding-grid security boundaries, using disposable synthetic fixtures.

The retained-policy fixtures deliberately represent an earlier restricted assessment
followed by a less restricted current source. No fixture grants a production approval.
"""
import csv
import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from test_auth_policy import env, login
from test_diligence import D, assessment
from test_document_workflow import BASE, allow_processing, candidate, upload
from test_observability_governance import post
from test_runtime_queue import published
from test_table_security_review import confirmed

T = '/api/v1/tables/findings'


def signed(http, name='lawyer'):
    response = login(http, name)
    assert response.status_code == 200, response.text
    return response.json()['csrf_token']


def manual(http, csrf, source, **changes):
    response = post(http, D + '/findings', csrf, assessment(source, **changes))
    assert response.status_code == 201, response.text
    return response.json()


def revise(http, csrf, source, finding, **changes):
    response = post(http, D + '/findings/' + finding['id'] + '/revisions', csrf,
                    assessment(source, expected_revision=finding['revision'], **changes))
    assert response.status_code == 201, response.text
    return response.json()


def pending_candidate(env, classification='ordinary'):
    from kestrel.services import jobs
    http, sessions, ids, _ = env
    version = published(http, ids)
    allow_processing(http, sessions, ids)
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'], classification=classification,
                       clean_team_scope='pricing' if classification == 'clean_team' else '')
    csrf = signed(http, 'sme')
    response = post(http, '/api/v1/jobs', csrf, {
        'playbook_id': version, 'document_version_id': source['id'],
        'idempotency_key': 'independent-pending-' + uuid4().hex,
        'rationale': 'Synthetic isolated offline candidate creation without a finding review decision.',
    })
    assert response.status_code == 201, response.text
    assert jobs.run_once(sessions)
    csrf = signed(http)
    response = http.get(BASE + '/findings', params={'matter_id': ids['matter']})
    assert response.status_code == 200 and response.json(), response.text
    finding = response.json()[0]
    assert finding['review_state'] == 'candidate'
    return source, finding, csrf


def membership(sessions, ids, person='lawyer', scope='pricing'):
    from kestrel.models import CleanTeamMembership
    from kestrel.services.auth import clock
    with sessions() as db:
        row = CleanTeamMembership(account_id=ids[person], matter_id=ids['matter'],
                                  scope=scope, approved_by=ids['sme'], expires_at=clock() + 3600)
        db.add(row)
        db.commit()


def revoke_membership(sessions, ids, person='lawyer'):
    from kestrel.models import CleanTeamMembership
    with sessions() as db:
        for row in db.scalars(select(CleanTeamMembership).where(
            CleanTeamMembership.account_id == ids[person], CleanTeamMembership.matter_id == ids['matter'],
        )):
            row.revoked = True
        db.commit()


def ordinary_source(sessions, source):
    """Represent a later lawful source relaxation; retained finding policies stay intact."""
    from kestrel.models import DocumentPolicyVersion, SourceVersion
    with sessions() as db:
        policy = db.get(DocumentPolicyVersion, db.get(SourceVersion, source['id']).policy_id)
        policy.classification = 'ordinary'
        policy.clean_team_scope = None
        db.commit()


def retained_history(env, *, owner=None):
    http, sessions, ids, _ = env
    membership(sessions, ids)
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'], classification='clean_team', clean_team_scope='pricing',
                       logical_key='RETAINED-' + uuid4().hex[:8], file_name='retained-clean-team-contract.txt')
    first = manual(http, csrf, source, owner_id=owner,
                   summary='Earlier pricing assessment contains retained confidential context.')
    ordinary_source(sessions, source)
    current = revise(http, csrf, source, first, owner_id=owner,
                     summary='Current ordinary assessment still derives from retained pricing context.')
    return source, first, current, csrf


def withheld(response, *private):
    assert response.status_code in {401, 403, 404, 409}, response.text
    assert 'recordsTotal' not in response.text and 'recordsFiltered' not in response.text
    assert 'content-disposition' not in response.headers
    for value in private:
        assert value not in response.text


def selection(matter, rows, **changes):
    return {'matter_id': matter, 'ids': [r['id'] for r in rows], 'format': 'csv',
            'finding_versions': {r['id']: r['revision_id'] for r in rows}, **changes}


def export_rows(response):
    assert response.status_code == 200, response.text
    return list(csv.DictReader(io.StringIO(response.text)))


def test_relaxed_latest_policy_cannot_launder_retained_revision_across_old_and_new_routes(env):
    http, sessions, ids, _ = env
    source, first, current, csrf = retained_history(env)
    visible_source = confirmed(http, csrf, ids['matter'], logical_key='PUBLIC-CONTEXT', file_name='ordinary-safe.txt')
    visible = manual(http, csrf, visible_source, summary='Ordinary permitted finding remains visible in the register.')
    revoke_membership(sessions, ids)

    response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'length': 1})
    assert response.status_code == 200, response.text
    assert response.json()['recordsTotal'] == response.json()['recordsFiltered'] == 1
    assert [r['id'] for r in response.json()['data']] == [visible['id']]
    for needle in [source['file_name'], first['summary'], current['summary']]:
        response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'search': needle[:128]})
        assert response.status_code == 200, response.text
        assert response.json()['recordsTotal'] == 1 and response.json()['recordsFiltered'] == 0
        assert response.json()['data'] == []
    old_list = http.get(BASE + '/findings', params={'matter_id': ids['matter'], 'historical': True})
    assert old_list.status_code == 200, old_list.text
    assert [r['id'] for r in old_list.json()] == [visible['id']]
    board = http.get(D + '/board', params={'matter_id': ids['matter']})
    assert board.status_code == 200, board.text
    assert current['id'] not in board.text and first['summary'] not in board.text
    for historical in [False, True]:
        detail = http.get(T + '/' + current['id'], params={
            'matter_id': ids['matter'], 'revision_id': current['revision_id'], 'historical': historical,
        })
        withheld(detail, source['file_name'], first['summary'], current['summary'])
    withheld(http.get(D + '/findings/' + current['id'] + '/history'), first['summary'], current['summary'])
    for params in [{'source_id': source['id']}, {'source_id': source['id'], 'finding_id': current['id']}]:
        withheld(http.get(D + '/owners', params=params), ids['sme'])
    denied_write = post(http, D + '/findings/' + current['id'] + '/revisions', csrf,
                        assessment(source, expected_revision=current['revision']))
    withheld(denied_write, first['summary'], current['summary'])
    exported = post(http, T + '/export', csrf, selection(ids['matter'], [visible, current]))
    assert [r['id'] for r in export_rows(exported)] == [visible['id']]
    assert exported.headers['x-export-unavailable-count'] == '1'
    assert current['id'] not in exported.text and current['summary'] not in exported.text


def test_original_ai_candidate_policy_remains_in_full_chain_after_lawyer_revision(env):
    from kestrel.models import DocumentPolicyVersion, SourceFinding
    http, sessions, ids, _ = env
    source, original, csrf = candidate(env)
    membership(sessions, ids)
    with sessions() as db:
        policy = db.get(DocumentPolicyVersion, db.get(SourceFinding, original['id']).policy_id)
        policy.classification = 'clean_team'
        policy.clean_team_scope = 'pricing'
        db.commit()
    current = revise(http, csrf, source, original)
    revoke_membership(sessions, ids)
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'finding_filters': {'historical': True}})
    assert response.status_code == 200, response.text
    assert response.json()['recordsTotal'] == response.json()['recordsFiltered'] == 0
    assert response.json()['data'] == []
    withheld(http.get(D + '/findings/' + current['id'] + '/history'), original['summary'], current['summary'])
    withheld(http.get(T + '/' + current['id'], params={
        'matter_id': ids['matter'], 'revision_id': current['revision_id'],
    }), original['summary'], current['summary'])
    response = post(http, T + '/export', csrf, selection(ids['matter'], [current]))
    assert export_rows(response) == [] and response.headers['x-export-unavailable-count'] == '1'


def test_extra_source_lineage_policy_cannot_be_removed_by_source_filter_or_history(env):
    from kestrel.models import LegalFindingRevision, PolicySource, SourceVersion
    http, sessions, ids, _ = env
    membership(sessions, ids)
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'], logical_key='LINEAGE-PUBLIC')
    protected = confirmed(http, csrf, ids['matter'], logical_key='LINEAGE-PRIVATE',
                          classification='clean_team', clean_team_scope='pricing')
    finding = manual(http, csrf, source)
    with sessions() as db:
        row = db.get(LegalFindingRevision, finding['revision_id'])
        db.add(PolicySource(artifact_id=row.policy_id, source_id=db.get(SourceVersion, protected['id']).policy_id))
        db.commit()
    revoke_membership(sessions, ids)
    for filters in [{}, {'source_id': source['id']}, {'historical': True, 'source_id': source['id']}]:
        response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'finding_filters': filters})
        assert response.status_code == 200, response.text
        assert response.json()['recordsTotal'] == response.json()['recordsFiltered'] == 0
        assert response.json()['data'] == []
    withheld(http.get(D + '/findings/' + finding['id'] + '/history'), finding['summary'])


def test_historical_source_selection_retains_clean_team_scope_and_exact_source_version(env):
    http, sessions, ids, _ = env
    source, _, finding, csrf = retained_history(env)
    newer = upload(http, csrf, ids['matter'], logical_key=source['logical_key'], previous_id=source['id'])
    assert newer.status_code == 201, newer.text
    for historical, expected in [(False, 0), (True, 1)]:
        response = post(http, T + '/query', csrf, {
            'matter_id': ids['matter'], 'finding_filters': {'historical': historical},
        })
        assert response.status_code == 200, response.text
        assert response.json()['recordsTotal'] == expected
        if historical:
            assert response.json()['data'][0]['source_id'] == source['id']
            assert response.json()['data'][0]['historical'] is True
    response = post(http, T + '/export', csrf, selection(ids['matter'], [finding], historical=True))
    assert [r['source_id'] for r in export_rows(response)] == [source['id']]
    revoke_membership(sessions, ids)
    response = post(http, T + '/query', csrf, {
        'matter_id': ids['matter'], 'finding_filters': {'historical': True},
    })
    assert response.status_code == 200, response.text
    assert response.json()['recordsTotal'] == response.json()['recordsFiltered'] == 0
    assert response.json()['data'] == []
    response = post(http, T + '/export', csrf, selection(ids['matter'], [finding], historical=True))
    assert export_rows(response) == [] and response.headers['x-export-unavailable-count'] == '1'


@pytest.mark.parametrize('person,origin', [
    ('root', 'https://firm.localhost'), ('bank', 'https://bank.localhost'), ('client', 'https://client.localhost'),
])
def test_root_and_external_portals_cannot_read_internal_finding_grid_or_export(env, person, origin):
    http, _, ids, app = env
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    finding = manual(http, csrf, source)
    with TestClient(app, base_url=origin) as actor:
        login_result = login(actor, person, origin=origin)
        assert login_result.status_code == 200, login_result.text
        headers = {'origin': origin, 'x-csrf-token': login_result.json()['csrf_token']}
        withheld(actor.post(T + '/query', json={'matter_id': ids['matter']}, headers=headers), finding['summary'])
        withheld(actor.post(T + '/export', json=selection(ids['matter'], [finding]), headers=headers), finding['summary'])
        withheld(actor.get(T + '/' + finding['id'], params={
            'matter_id': ids['matter'], 'revision_id': finding['revision_id'],
        }), finding['summary'])
        withheld(actor.get(D + '/findings/' + finding['id'] + '/history'), finding['summary'])


def test_two_authorized_matters_still_cannot_mix_finding_selection_or_detail(env):
    from kestrel.models import MatterAssignment
    from kestrel.services.auth import clock
    http, sessions, ids, _ = env
    with sessions() as db:
        db.add(MatterAssignment(account_id=ids['lawyer'], matter_id=ids['other'], expires_at=clock() + 3600))
        db.commit()
    csrf = signed(http)
    own = manual(http, csrf, confirmed(http, csrf, ids['matter'], logical_key='MATTER-OWN'))
    foreign = manual(http, csrf, confirmed(http, csrf, ids['other'], logical_key='MATTER-FOREIGN'),
                     summary='Foreign matter private assessment must not enter the requested response.')
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'search': foreign['summary']})
    assert response.status_code == 200, response.text
    assert response.json()['recordsTotal'] == 1 and response.json()['recordsFiltered'] == 0
    assert response.json()['data'] == []
    response = post(http, T + '/export', csrf, selection(ids['matter'], [own, foreign]))
    assert [r['id'] for r in export_rows(response)] == [own['id']]
    assert response.headers['x-export-unavailable-count'] == '1'
    assert foreign['id'] not in response.text and foreign['summary'] not in response.text
    withheld(http.get(T + '/' + foreign['id'], params={
        'matter_id': ids['matter'], 'revision_id': foreign['revision_id'],
    }), foreign['summary'], foreign['source_id'])


def test_selected_exports_pin_exact_revision_and_do_not_silently_export_latest(env):
    http, _, ids, _ = env
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    old = manual(http, csrf, source, summary='Earlier displayed assessment awaiting a new lawyer correction.')
    current = revise(http, csrf, source, old, summary='Newly corrected confidential assessment was not selected by the user.')
    other = manual(http, csrf, source, summary='Separate explicitly selected assessment remains exportable.')
    response = post(http, T + '/export', csrf, selection(ids['matter'], [old, other]))
    assert [r['id'] for r in export_rows(response)] == [other['id']]
    assert response.headers['x-export-unavailable-count'] == '1'
    assert old['summary'] not in response.text and current['summary'] not in response.text
    withheld(http.get(T + '/' + old['id'], params={
        'matter_id': ids['matter'], 'revision_id': old['revision_id'],
    }), current['summary'])
    for versions in [None, {}, {old['id']: old['revision_id'], str(uuid4()): current['revision_id']}]:
        body = selection(ids['matter'], [old])
        if versions is None:
            body.pop('finding_versions')
        else:
            body['finding_versions'] = versions
        assert post(http, T + '/export', csrf, body).status_code == 422


@pytest.mark.parametrize('field,value', [
    ('source_filters', {'historical': True}), ('financial_filters', {'entity': 'private entity'}),
    ('task_filters', {'mine': True}), ('saved_view_id', 'private-inventory-view'),
])
def test_finding_grid_rejects_cross_dataset_scope_and_ungoverned_saved_view(env, field, value):
    http, _, ids, _ = env
    csrf = signed(http)
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], field: value})
    assert response.status_code == 422, response.text
    for view in ['inventory', 'financial', 'tasks']:
        response = post(http, '/api/v1/tables/' + view + '/query', csrf, {
            'matter_id': ids['matter'], 'finding_filters': {'historical': True},
        })
        assert response.status_code == 422, response.text


def test_owner_must_clear_every_retained_revision_even_when_current_source_is_ordinary(env):
    from kestrel.models import LegalFindingRevision
    http, sessions, ids, _ = env
    source, _, current, csrf = retained_history(env)
    owners = http.get(D + '/owners', params={'source_id': source['id'], 'finding_id': current['id']})
    assert owners.status_code == 200, owners.text
    assert ids['sme'] not in {r['id'] for r in owners.json()}
    with sessions() as db:
        count = db.scalar(select(func.count()).select_from(LegalFindingRevision))
    response = post(http, D + '/findings/' + current['id'] + '/revisions', csrf,
                    assessment(source, expected_revision=current['revision'], owner_id=ids['sme']))
    assert response.status_code in {403, 422}, response.text
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(LegalFindingRevision)) == count


def test_now_ineligible_owner_identity_is_masked_without_hiding_actor_permitted_finding(env):
    http, sessions, ids, _ = env
    membership(sessions, ids, 'sme')
    source, _, current, csrf = retained_history(env, owner=ids['sme'])
    revoke_membership(sessions, ids, 'sme')
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter']})
    assert response.status_code == 200, response.text
    row = response.json()['data'][0]
    assert row['id'] == current['id'] and row['owner_id'] is None and row['owner'] is None
    searched = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'column_filters': {'owner': 'sme'}})
    assert searched.status_code == 200, searched.text
    assert searched.json()['recordsTotal'] == 1 and searched.json()['recordsFiltered'] == 0
    detail = http.get(T + '/' + current['id'], params={
        'matter_id': ids['matter'], 'revision_id': current['revision_id'],
    })
    assert detail.status_code == 200, detail.text
    assert detail.json()['finding']['owner_id'] is None and detail.json()['finding']['owner'] is None
    assert ids['sme'] not in {r['id'] for r in detail.json()['eligible_owners']}
    history = http.get(D + '/findings/' + current['id'] + '/history')
    assert history.status_code == 200, history.text
    assert all(r['owner_id'] is None and r['owner'] is None for r in history.json())


def test_permitted_selected_finding_stays_editable_while_unrelated_source_profile_is_withheld(env):
    http, sessions, ids, _ = env
    source, _, hidden, csrf = retained_history(env)
    visible = manual(http, csrf, source,
                     summary='Independent ordinary assessment can be reviewed without the earlier pricing finding.')
    revoke_membership(sessions, ids)
    response = http.get(T + '/' + visible['id'], params={
        'matter_id': ids['matter'], 'revision_id': visible['revision_id'],
    })
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['finding']['id'] == visible['id']
    assert value['finding']['revision_id'] == visible['revision_id']
    assert value['source'] is None and value['source_review_available'] is False
    assert value['source_review_notice']
    assert ids['lawyer'] in {r['id'] for r in value['eligible_owners']}
    assert 'finding_progress' not in response.text
    assert hidden['id'] not in response.text and hidden['summary'] not in response.text
    profile = http.get(T + '/source-profile/' + source['id'], params={'matter_id': ids['matter']})
    assert profile.status_code == 200, profile.text
    assert profile.json()['source'] is None and profile.json()['source_review_available'] is False
    assert profile.json()['eligible_owners'] == []
    assert hidden['id'] not in profile.text and hidden['summary'] not in profile.text


@pytest.mark.parametrize('change', ['session', 'account', 'role', 'wall', 'clean_team'])
def test_finding_query_withholds_after_actor_authority_changes_during_preparation(env, monkeypatch, change):
    from kestrel.models import Account, EthicalWall, RoleGrant, ServerSession
    from kestrel.services import data_tables as tables
    http, sessions, ids, _ = env
    if change == 'clean_team':
        _, _, finding, csrf = retained_history(env)
    else:
        csrf = signed(http)
        finding = manual(http, csrf, confirmed(http, csrf, ids['matter']))
    original = tables.collect
    fired = False

    def collect_then_revoke(db, actor, view, payload):
        nonlocal fired
        rows = original(db, actor, view, payload)
        if view == 'findings' and not fired:
            fired = True
            with sessions() as writer:
                if change == 'session':
                    writer.scalar(select(ServerSession).where(ServerSession.account_id == ids['lawyer'])).revoked = True
                elif change == 'account':
                    writer.get(Account, ids['lawyer']).active = False
                elif change == 'role':
                    writer.execute(delete(RoleGrant).where(RoleGrant.account_id == ids['lawyer']))
                elif change == 'wall':
                    writer.add(EthicalWall(account_id=ids['lawyer'], matter_id=ids['matter']))
                else:
                    from kestrel.models import CleanTeamMembership
                    writer.scalar(select(CleanTeamMembership).where(
                        CleanTeamMembership.account_id == ids['lawyer'],
                    )).revoked = True
                writer.commit()
        return rows

    monkeypatch.setattr(tables, 'collect', collect_then_revoke)
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter']})
    assert fired
    withheld(response, finding['id'], finding['summary'])


@pytest.mark.parametrize('operation', ['query', 'csv', 'xlsx'])
def test_owner_clearance_revocation_during_preparation_withholds_counts_and_files(env, monkeypatch, operation):
    from kestrel.services import data_tables as tables
    http, sessions, ids, _ = env
    membership(sessions, ids, 'sme')
    _, _, finding, csrf = retained_history(env, owner=ids['sme'])
    name = 'collect' if operation == 'query' else 'selected'
    original = getattr(tables, name)
    fired = False

    def collect_then_revoke(*args, **kwargs):
        nonlocal fired
        rows = original(*args, **kwargs)
        if not fired:
            fired = True
            revoke_membership(sessions, ids, 'sme')
        return rows

    monkeypatch.setattr(tables, name, collect_then_revoke)
    body = {'matter_id': ids['matter']} if operation == 'query' else selection(ids['matter'], [finding], format=operation)
    response = post(http, T + ('/query' if operation == 'query' else '/export'), csrf, body)
    assert fired
    withheld(response, finding['id'], finding['summary'], ids['sme'])


@pytest.mark.parametrize('endpoint', ['history', 'board'])
def test_old_diligence_reads_reauthenticate_after_preparing_response(env, monkeypatch, endpoint):
    from kestrel.models import EthicalWall
    from kestrel.services import diligence
    http, sessions, ids, _ = env
    csrf = signed(http)
    finding = manual(http, csrf, confirmed(http, csrf, ids['matter']))
    original = getattr(diligence, endpoint)
    fired = False

    def prepare_then_wall(*args, **kwargs):
        nonlocal fired
        # Keep the first preparation read-only so a second SQLite connection
        # can commit the revocation. Receipt persistence is tested separately.
        kwargs['audited'] = False
        result = original(*args, **kwargs)
        if not fired:
            fired = True
            with sessions() as writer:
                writer.add(EthicalWall(account_id=ids['lawyer'], matter_id=ids['matter']))
                writer.commit()
        return result

    monkeypatch.setattr(diligence, endpoint, prepare_then_wall)
    path = D + '/board' if endpoint == 'board' else D + '/findings/' + finding['id'] + '/history'
    response = http.get(path, params={'matter_id': ids['matter']} if endpoint == 'board' else None)
    assert fired
    withheld(response, finding['id'], finding['summary'])


def test_legacy_owner_picker_withholds_prepared_people_after_target_becomes_inactive(env, monkeypatch):
    from kestrel.models import Account
    from kestrel.services import finding_tables
    http, sessions, ids, _ = env
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    finding = manual(http, csrf, source)
    original = finding_tables.owners
    fired = False

    def owners_then_revoke(*args, **kwargs):
        nonlocal fired
        result = original(*args, **kwargs)
        if not fired:
            fired = True
            assert ids['sme'] in {row['id'] for row in result}
            with sessions() as writer:
                writer.get(Account, ids['sme']).active = False
                writer.commit()
        return result

    monkeypatch.setattr(finding_tables, 'owners', owners_then_revoke)
    response = http.get(D + '/owners', params={'source_id': source['id'], 'finding_id': finding['id']})
    assert fired
    withheld(response, ids['sme'])


def test_legacy_analyzed_source_sanitizes_unproven_metadata_but_keeps_exact_finding_editor(env):
    http, _, ids, _ = env
    source, finding, _ = candidate(env)
    response = http.get(T + '/' + finding['id'], params={
        'matter_id': ids['matter'], 'revision_id': finding['revision_id'],
    })
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['finding']['id'] == finding['id']
    assert value['finding']['revision_id'] == finding['revision_id']
    assert value['can_edit'] is True
    assert value['source_review_available'] is True and value['source']['id'] == source['id']
    assert value['source_review_notice']
    analysis = value['source']['analysis']
    assert analysis['state'] == 'unavailable' and analysis['metadata_withheld'] is True
    assert analysis['has_completed_run'] is None and analysis['coverage'] == []
    assert source['id'] == value['finding']['source_id']


def test_frozen_matter_retains_readable_finding_but_rejects_new_revision(env):
    from kestrel.models import LegalFindingRevision, MatterLifecycle
    http, sessions, ids, _ = env
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    finding = manual(http, csrf, source)
    with sessions() as db:
        db.add(MatterLifecycle(matter_id=ids['matter'], frozen=True))
        db.commit()
    response = http.get(T + '/' + finding['id'], params={
        'matter_id': ids['matter'], 'revision_id': finding['revision_id'],
    })
    assert response.status_code == 200, response.text
    assert response.json()['can_edit'] is False
    response = post(http, D + '/findings/' + finding['id'] + '/revisions', csrf,
                    assessment(source, expected_revision=finding['revision']))
    assert response.status_code == 409, response.text
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(LegalFindingRevision)) == 1


def test_legacy_board_cannot_disclose_unproven_private_document_review_after_source_relaxation(env):
    http, sessions, ids, _ = env
    membership(sessions, ids)
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'], classification='clean_team', clean_team_scope='pricing')
    private_title = 'Retained private pricing strategy review'
    private_party = 'Confidential pricing counterparty canary'
    response = post(http, D + '/documents/' + source['id'] + '/reviews', csrf, {
        'expected_revision': 0, 'title': private_title, 'counterparty': private_party,
        'scope': 'supplier', 'coverage_state': 'in_review',
        'rationale': 'Synthetic restricted source review predates a later source relaxation.',
    })
    assert response.status_code == 201, response.text
    ordinary_source(sessions, source)
    revoke_membership(sessions, ids)
    response = http.get(D + '/board', params={'matter_id': ids['matter']})
    assert response.status_code == 200, response.text
    assert private_title not in response.text and private_party not in response.text
    for row in response.json()['sources']:
        if row['id'] == source['id']:
            assert row.get('document_review', {}).get('coverage_state') not in {'not_started', 'complete'}


def test_direct_document_review_cannot_mark_complete_while_a_same_source_finding_chain_is_hidden(env):
    from kestrel.models import DocumentReviewVersion
    http, sessions, ids, _ = env
    source, _, hidden, csrf = retained_history(env)
    revoke_membership(sessions, ids)
    response = post(http, D + '/documents/' + source['id'] + '/reviews', csrf, {
        'expected_revision': 0, 'title': 'Current ordinary whole-document completion attempt',
        'counterparty': '', 'scope': 'customer', 'coverage_state': 'complete',
        'rationale': 'A restricted same-source assessment must not disappear from completion authority.',
    })
    assert response.status_code in {403, 409}, response.text
    assert hidden['id'] not in response.text and hidden['summary'] not in response.text
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(DocumentReviewVersion)) == 0


def test_legacy_workflow_candidate_review_cannot_bypass_original_retained_policy(env):
    from kestrel.models import FindingReview
    http, sessions, ids, _ = env
    membership(sessions, ids)
    membership(sessions, ids, 'sme')
    source, finding, csrf = pending_candidate(env, 'clean_team')
    ordinary_source(sessions, source)
    revoke_membership(sessions, ids)
    response = http.get(BASE + '/findings', params={'matter_id': ids['matter'], 'historical': True})
    assert response.status_code == 200 and response.json() == [], response.text
    response = post(http, BASE + '/findings/' + finding['id'] + '/review', csrf, {
        'decision': 'reviewed', 'rationale': 'Current ordinary source cannot clear a retained pricing candidate.',
    })
    withheld(response, finding['summary'])
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(FindingReview)) == 0


def test_legacy_workflow_candidate_review_rechecks_actor_before_committing_decision(env, monkeypatch):
    from kestrel.models import EthicalWall, FindingReview
    from kestrel.services import workflow
    http, sessions, ids, _ = env
    _, finding, csrf = pending_candidate(env)
    original = workflow.finding
    fired = False

    def authorize_then_wall(*args, **kwargs):
        nonlocal fired
        result = original(*args, **kwargs)
        if not fired:
            fired = True
            with sessions() as writer:
                writer.add(EthicalWall(account_id=ids['lawyer'], matter_id=ids['matter']))
                writer.commit()
        return result

    monkeypatch.setattr(workflow, 'finding', authorize_then_wall)
    response = post(http, BASE + '/findings/' + finding['id'] + '/review', csrf, {
        'decision': 'reviewed', 'rationale': 'A revoked actor cannot commit a legal candidate decision.',
    })
    assert fired
    withheld(response, finding['summary'])
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(FindingReview)) == 0


def test_legacy_workflow_finding_list_rechecks_visible_owner_identity_after_preparation(env, monkeypatch):
    from kestrel.models import Account
    from kestrel.services import diligence
    http, sessions, ids, _ = env
    csrf = signed(http)
    finding = manual(http, csrf, confirmed(http, csrf, ids['matter']), owner_id=ids['sme'])
    original = diligence.visible_findings
    fired = False

    def visible_then_revoke(db, actor, matter, historical=False, audited=True):
        nonlocal fired
        rows = original(db, actor, matter, historical, audited=False)
        if not fired:
            fired = True
            assert rows[0]['owner_id'] == ids['sme']
            with sessions() as writer:
                writer.get(Account, ids['sme']).active = False
                writer.commit()
        return rows

    monkeypatch.setattr(diligence, 'visible_findings', visible_then_revoke)
    response = http.get(BASE + '/findings', params={'matter_id': ids['matter']})
    assert fired
    withheld(response, finding['id'], ids['sme'])


@pytest.mark.parametrize('change', ['actor', 'owner'])
def test_legacy_revision_save_rolls_back_if_actor_or_owner_is_revoked_after_evidence_check(env, monkeypatch, change):
    from kestrel.models import Account, DocumentPolicyVersion, EthicalWall, LegalFindingRevision
    from kestrel.services import diligence
    http, sessions, ids, _ = env
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    finding = manual(http, csrf, source, owner_id=ids['sme'])
    with sessions() as db:
        counts = tuple(db.scalar(select(func.count()).select_from(model))
                       for model in [LegalFindingRevision, DocumentPolicyVersion])
    original = diligence.evidence
    fired = False

    def evidence_then_revoke(*args, **kwargs):
        nonlocal fired
        result = original(*args, **kwargs)
        if not fired:
            fired = True
            with sessions() as writer:
                if change == 'actor':
                    writer.add(EthicalWall(account_id=ids['lawyer'], matter_id=ids['matter']))
                else:
                    writer.get(Account, ids['sme']).active = False
                writer.commit()
        return result

    monkeypatch.setattr(diligence, 'evidence', evidence_then_revoke)
    response = post(http, D + '/findings/' + finding['id'] + '/revisions', csrf,
                    assessment(source, expected_revision=finding['revision'], owner_id=ids['sme']))
    assert fired
    assert response.status_code in {401, 403, 409, 422}, response.text
    assert 'revision_id' not in response.text and finding['summary'] not in response.text
    with sessions() as db:
        assert tuple(db.scalar(select(func.count()).select_from(model))
                     for model in [LegalFindingRevision, DocumentPolicyVersion]) == counts


@pytest.mark.parametrize('format', ['csv', 'xlsx'])
def test_successful_selected_export_excludes_hidden_chain_and_treats_formula_text_as_literal(env, format):
    http, sessions, ids, _ = env
    _, _, hidden, csrf = retained_history(env)
    source = confirmed(http, csrf, ids['matter'], logical_key='FORMULA-SAFE')
    visible = manual(http, csrf, source, summary='=SUM(1,2) is untrusted synthetic finding text.')
    revoke_membership(sessions, ids)
    response = post(http, T + '/export', csrf, selection(ids['matter'], [visible, hidden], format=format))
    assert response.status_code == 200, response.text
    assert response.headers['x-export-unavailable-count'] == '1'
    if format == 'csv':
        rows = export_rows(response)
        assert [r['id'] for r in rows] == [visible['id']]
        assert rows[0]['summary'] == "'" + visible['summary']
    else:
        from openpyxl import load_workbook
        with io.BytesIO(response.content) as data:
            book = load_workbook(data)
            sheet = book.active
            columns = [cell.value for cell in sheet[1]]
            assert sheet.max_row == 2
            assert sheet.cell(2, columns.index('id') + 1).value == visible['id']
            cell = sheet.cell(2, columns.index('summary') + 1)
            assert cell.value == visible['summary'] and cell.data_type == 's'
            assert hidden['id'] not in {cell.value for row in sheet for cell in row}
            book.close()
