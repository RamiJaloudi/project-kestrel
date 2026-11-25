"""Independent task-table boundaries; disposable synthetic SQLite/PG fixtures only."""
import csv
import hashlib
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from test_auth_policy import env, login
from test_observability_governance import post
from test_table_security_review import confirmed

T = '/api/v1/tables/tasks'
W = '/api/v1/review-work'


def signed(http, name='lawyer', origin='https://firm.localhost'):
    response = login(http, name, origin)
    assert response.status_code == 200, response.text
    return response.json()['csrf_token']


def create_task(http, csrf, matter, assignee, key, **source_changes):
    source = confirmed(http, csrf, matter, logical_key=key.upper(), file_name=key + '.txt', **source_changes)
    response = post(http, W + '/sources/' + source['id'] + '/tasks', csrf, {
        'stage': 'review', 'assignee_id': assignee, 'request_key': 'task-' + key,
        'rationale': 'Create synthetic source coordination for independent security checks',
    })
    assert response.status_code == 201, response.text
    return source, response.json()


def scopes(sessions, ids, accounts, *names):
    from kestrel.models import CleanTeamMembership
    from kestrel.services.auth import clock
    with sessions() as db:
        for account in accounts:
            for name in names:
                db.add(CleanTeamMembership(account_id=account, matter_id=ids['matter'], scope=name,
                                           approved_by=ids['sme'], expires_at=clock() + 3600))
        db.commit()


def ordinary(sessions, source):
    from kestrel.models import DocumentPolicyVersion, SourceVersion
    # Fixture models an authorized relaxation. Retained task/event captures must
    # remain separate from the current source's ordinary classification.
    with sessions() as db:
        policy = db.get(DocumentPolicyVersion, db.get(SourceVersion, source['id']).policy_id)
        policy.classification = 'ordinary'
        policy.clean_team_scope = None
        db.commit()


def two_scope_history(http, csrf, sessions, ids, key):
    from kestrel.models import DocumentPolicyVersion, SourceVersion
    from kestrel.services.auth import clock
    source, task = create_task(http, csrf, ids['matter'], ids['lawyer'], key,
                               classification='clean_team', clean_team_scope='pricing')
    with sessions() as db:
        policy = db.get(DocumentPolicyVersion, db.get(SourceVersion, source['id']).policy_id)
        policy.clean_team_scope = 'strategy'
        db.commit()
    response = post(http, W + '/tasks/' + task['id'] + '/events', csrf, {
        'operation': 'deadline', 'expected_revision': 1, 'due_at': clock() + 600,
        'request_key': key + '-strategy-event',
        'rationale': 'STRATEGY_EVENT_PRIVATE_CANARY retained independently of pricing root',
    })
    assert response.status_code == 201, response.text
    ordinary(sessions, source)
    return source, response.json()


def command(ids, tasks, **changes):
    return {
        'matter_id': ids['matter'],
        'items': [{'id': task['id'], 'expected_revision': task['revision']} for task in tasks],
        'assignee_id': ids['sme'], 'request_key': str(uuid.uuid4()),
        'rationale': 'Reassign explicitly selected synthetic current coordination tasks',
        **changes,
    }


def withheld(response, *private):
    assert response.status_code in {401, 403, 404, 409}, response.text
    assert 'recordsTotal' not in response.text and 'recordsFiltered' not in response.text
    assert 'content-disposition' not in response.headers
    for value in private:
        assert value not in response.text


def task_counts(sessions, tid):
    from kestrel.models import ReviewTaskEvent, ReviewTaskNotification
    with sessions() as db:
        return (
            db.scalar(select(func.count()).select_from(ReviewTaskEvent).where(ReviewTaskEvent.task_id == tid)),
            db.scalar(select(func.count()).select_from(ReviewTaskNotification).where(ReviewTaskNotification.task_id == tid)),
        )


@pytest.mark.parametrize('dataset', ['inventory', 'financial'])
def test_existing_saved_view_cannot_be_reinterpreted_as_task_configuration(env, dataset):
    http, _, ids, _ = env
    csrf = signed(http)
    created = post(http, '/api/v1/table-views', csrf, {
        'matter_id': ids['matter'], 'dataset': dataset, 'name': 'PRIVATE_OLD_DATASET_CONFIG',
        'query': {'matter_id': ids['matter']}, 'handling': 'private_unclassified', 'evidence_refs': [],
        'rationale': 'Preserve the existing saved-view dataset contract without a schema alias',
        'request_key': 'independent-old-' + dataset,
    })
    assert created.status_code == 201, created.text
    view = created.json()
    response = post(http, T + '/query', csrf, {
        'matter_id': ids['matter'], 'saved_view_id': view['id'],
        'saved_view_version_hash': view['version_hash'],
    })
    assert response.status_code == 422, response.text
    assert 'recordsTotal' not in response.text and 'PRIVATE_OLD_DATASET_CONFIG' not in response.text
    response = post(http, '/api/v1/table-views', csrf, {
        'matter_id': ids['matter'], 'dataset': 'tasks', 'name': 'Unsupported task configuration',
        'query': {'matter_id': ids['matter']},
        'rationale': 'Task evidence requires a separate reviewed additive migration',
        'request_key': 'independent-task-no-alias',
    })
    assert response.status_code == 422, response.text


def test_task_counts_search_and_files_require_root_and_every_retained_event_scope(env):
    from kestrel.models import CleanTeamMembership
    http, sessions, ids, _ = env
    scopes(sessions, ids, [ids['lawyer']], 'pricing', 'strategy')
    csrf = signed(http)
    hidden_source, hidden = two_scope_history(http, csrf, sessions, ids, 'retained-union-secret')
    visible_source, visible = create_task(http, csrf, ids['matter'], ids['lawyer'], 'visible-coordination')
    with sessions() as db:
        db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id == ids['lawyer'],
                  CleanTeamMembership.scope == 'strategy')).revoked = True
        db.commit()
    # Current ordinary source and original pricing capture remain authorized;
    # the later strategy event alone excludes the complete derived task.
    assert http.get('/api/v1/workflow/documents/' + hidden_source['id']).status_code == 200
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter']})
    assert response.status_code == 200, response.text
    assert response.json()['recordsTotal'] == response.json()['recordsFiltered'] == 1
    assert [row['id'] for row in response.json()['data']] == [visible['id']]
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'search': hidden_source['file_name']})
    assert response.status_code == 200 and response.json()['recordsTotal'] == 1
    assert response.json()['recordsFiltered'] == 0 and response.json()['data'] == []
    assert hidden['id'] not in response.text and hidden_source['file_name'] not in response.text
    for kind in ['csv', 'xlsx']:
        response = post(http, T + '/export', csrf, {
            'matter_id': ids['matter'], 'ids': [hidden['id'], visible['id']], 'format': kind,
        })
        assert response.status_code == 200, response.text
        assert response.headers['x-export-unavailable-count'] == '1'
        if kind == 'csv':
            rows = list(csv.DictReader(io.StringIO(response.text)))
        else:
            from openpyxl import load_workbook
            book = load_workbook(io.BytesIO(response.content), data_only=False)
            values = list(book.active.values)
            rows = [dict(zip(values[0], row)) for row in values[1:]]
            book.close()
        assert [row['id'] for row in rows] == [visible['id']]
        assert hidden['id'] not in str(rows) and hidden_source['file_name'] not in str(rows)
        assert 'STRATEGY_EVENT_PRIVATE_CANARY' not in str(rows)


def test_fully_cleared_two_matter_actor_cannot_mix_task_response_or_bulk_scope(env):
    from kestrel.models import MatterAssignment
    from kestrel.services.auth import clock
    http, sessions, ids, _ = env
    with sessions() as db:
        for uid in [ids['lawyer'], ids['sme']]:
            db.add(MatterAssignment(account_id=uid, matter_id=ids['other'], expires_at=clock() + 3600))
        db.commit()
    csrf = signed(http)
    _, own = create_task(http, csrf, ids['matter'], ids['lawyer'], 'scope-own-task')
    foreign_source, foreign = create_task(http, csrf, ids['other'], ids['lawyer'], 'foreign-task-private')
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter'], 'search': foreign_source['file_name']})
    assert response.status_code == 200, response.text
    assert response.json()['recordsTotal'] == 1 and response.json()['recordsFiltered'] == 0
    assert foreign['id'] not in response.text and foreign_source['file_name'] not in response.text
    response = post(http, T + '/export', csrf, {
        'matter_id': ids['matter'], 'ids': [own['id'], foreign['id']], 'format': 'csv',
    })
    assert response.status_code == 200 and response.headers['x-export-unavailable-count'] == '1'
    assert [row['id'] for row in csv.DictReader(io.StringIO(response.text))] == [own['id']]
    selected = command(ids, [own, foreign])
    response = post(http, T + '/eligible-people', csrf, {'matter_id': ids['matter'], 'items': selected['items']})
    withheld(response, foreign['id'], foreign_source['file_name'])
    response = post(http, T + '/bulk-reassign', csrf, selected)
    assert response.status_code == 200, response.text
    assert (response.json()['succeeded'], response.json()['unavailable']) == (1, 1)
    assert [row['id'] for row in response.json()['results']] == [own['id']]
    assert foreign['id'] not in response.text and foreign_source['file_name'] not in response.text
    assert task_counts(sessions, foreign['id'])[0] == 1


@pytest.mark.parametrize('name,host', [('root', 'firm'), ('bank', 'bank'), ('client', 'client')])
def test_root_and_external_roles_have_no_internal_task_table_or_bulk_override(env, name, host):
    http, _, ids, app = env
    csrf = signed(http)
    source, task = create_task(http, csrf, ids['matter'], ids['lawyer'], 'internal-task-pii')
    origin = 'https://' + host + '.localhost'
    with TestClient(app, base_url=origin) as actor_http:
        token = signed(actor_http, name, origin)
        requests = [
            ('/query', {'matter_id': ids['matter']}),
            ('/export', {'matter_id': ids['matter'], 'ids': [task['id']], 'format': 'csv'}),
            ('/eligible-people', {'matter_id': ids['matter'], 'items': [{'id': task['id'], 'expected_revision': 1}]}),
            ('/bulk-reassign', command(ids, [task])),
        ]
        for path, body in requests:
            response = post(actor_http, T + path, token, body)
            assert response.status_code == 403, response.text
            withheld(response, task['id'], source['file_name'])


def test_mixed_bulk_response_and_replay_do_not_echo_denied_stale_or_missing_tasks(env):
    from kestrel.models import CleanTeamMembership
    http, sessions, ids, _ = env
    scopes(sessions, ids, [ids['lawyer']], 'pricing')
    csrf = signed(http)
    _, good = create_task(http, csrf, ids['matter'], ids['lawyer'], 'bulk-current-good')
    _, stale = create_task(http, csrf, ids['matter'], ids['lawyer'], 'bulk-stale-private')
    response = post(http, W + '/tasks/' + stale['id'] + '/events', csrf, {
        'operation': 'accept', 'expected_revision': 1, 'request_key': 'advance-stale-task',
        'rationale': 'STALE_HISTORY_PRIVATE_CANARY must not enter a bulk failure explanation',
    })
    assert response.status_code == 201, response.text
    hidden_source, hidden = create_task(http, csrf, ids['matter'], ids['lawyer'], 'bulk-denied-private',
                                        classification='clean_team', clean_team_scope='pricing')
    ordinary(sessions, hidden_source)
    with sessions() as db:
        db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id == ids['lawyer'])).revoked = True
        db.commit()
    missing = str(uuid.uuid4())
    payload = command(ids, [good, stale, hidden])
    payload['items'].append({'id': missing, 'expected_revision': 1})
    before = {task['id']: task_counts(sessions, task['id']) for task in [good, stale, hidden]}
    response = post(http, T + '/bulk-reassign', csrf, payload)
    assert response.status_code == 200, response.text
    value = response.json()
    assert set(value) == {'requested', 'succeeded', 'unavailable', 'results'}
    assert (value['requested'], value['succeeded'], value['unavailable']) == (4, 1, 3)
    assert value['results'] == [{'id': good['id'], 'revision': 2, 'status': 'reassigned'}]
    for private in [stale['id'], hidden['id'], missing, hidden_source['file_name'], 'STALE_HISTORY_PRIVATE_CANARY']:
        assert private not in response.text
    assert task_counts(sessions, stale['id']) == before[stale['id']]
    assert task_counts(sessions, hidden['id']) == before[hidden['id']]
    committed = task_counts(sessions, good['id'])
    response = post(http, T + '/bulk-reassign', csrf, payload)
    assert response.status_code == 200 and response.json()['results'][0]['status'] == 'replayed'
    assert task_counts(sessions, good['id']) == committed


def test_target_must_clear_every_selected_task_and_historical_event_scope(env):
    http, sessions, ids, _ = env
    scopes(sessions, ids, [ids['lawyer']], 'pricing', 'strategy')
    scopes(sessions, ids, [ids['sme']], 'pricing')
    csrf = signed(http)
    _, good = create_task(http, csrf, ids['matter'], ids['lawyer'], 'target-current-ordinary')
    _, union = two_scope_history(http, csrf, sessions, ids, 'target-two-scope-task')
    payload = command(ids, [good, union])
    response = post(http, T + '/eligible-people', csrf, {'matter_id': ids['matter'], 'items': payload['items']})
    assert response.status_code == 200, response.text
    assert ids['sme'] not in {person['id'] for person in response.json()}
    before = task_counts(sessions, union['id'])
    response = post(http, T + '/bulk-reassign', csrf, payload)
    assert response.status_code == 200, response.text
    assert (response.json()['succeeded'], response.json()['unavailable']) == (1, 1)
    assert [row['id'] for row in response.json()['results']] == [good['id']]
    assert union['id'] not in response.text and 'strategy' not in response.text.casefold()
    assert task_counts(sessions, union['id']) == before


def test_current_assignee_without_creator_or_sme_authority_cannot_manage_task(env):
    http, sessions, ids, _ = env
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'], logical_key='OTHER-CREATOR', file_name='other-creator.txt')
    token = signed(http, 'sme')
    response = post(http, W + '/sources/' + source['id'] + '/tasks', token, {
        'stage': 'qc', 'assignee_id': ids['lawyer'], 'request_key': 'independent-sme-created-task',
        'rationale': 'SME creates coordination; assignee activity does not confer management authority',
    })
    assert response.status_code == 201, response.text
    task = response.json(); csrf = signed(http)
    response = post(http, T + '/query', csrf, {'matter_id': ids['matter']})
    assert response.status_code == 200 and response.json()['data'][0]['can_reassign'] is False
    before = task_counts(sessions, task['id'])
    response = post(http, T + '/bulk-reassign', csrf, command(ids, [task]))
    assert response.status_code == 200 and response.json()['results'] == []
    assert response.json()['unavailable'] == 1 and task['id'] not in response.text
    assert task_counts(sessions, task['id']) == before


@pytest.mark.parametrize('operation,change', [
    ('query', 'wall'), ('query', 'role'), ('query', 'session'), ('csv', 'account'), ('xlsx', 'wall'),
    ('query', 'target'), ('xlsx', 'target'), ('query', 'membership'),
])
def test_prepared_task_counts_and_files_are_withheld_after_identity_revocation(env, monkeypatch, operation, change):
    from kestrel.models import Account, CleanTeamMembership, EthicalWall, RoleGrant, ServerSession
    from kestrel.services import data_tables as tables
    http, sessions, ids, _ = env
    if change == 'membership': scopes(sessions, ids, [ids['lawyer']], 'pricing')
    csrf = signed(http)
    source, task = create_task(http, csrf, ids['matter'], ids['sme'] if change == 'target' else ids['lawyer'],
        'mid-identity-private', **({'classification': 'clean_team', 'clean_team_scope': 'pricing'} if change == 'membership' else {}))
    original = tables.collect if operation == 'query' else tables.selected
    done = False
    def revoke_after_prepare(db, actor, view, payload):
        nonlocal done
        value = original(db, actor, view, payload)
        if not done:
            done = True
            with sessions() as writer:
                if change == 'wall': writer.add(EthicalWall(account_id=ids['lawyer'], matter_id=ids['matter'], active=True))
                elif change == 'role': writer.execute(delete(RoleGrant).where(RoleGrant.account_id == ids['lawyer']))
                elif change in {'account', 'target'}: writer.get(Account, ids['sme'] if change == 'target' else ids['lawyer']).active = False
                elif change == 'membership': writer.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id == ids['lawyer'])).revoked = True
                else: writer.scalar(select(ServerSession).where(ServerSession.account_id == ids['lawyer'])).revoked = True
                writer.commit()
        return value
    monkeypatch.setattr(tables, 'collect' if operation == 'query' else 'selected', revoke_after_prepare)
    body = {'matter_id': ids['matter']}
    if operation != 'query': body.update(ids=[task['id']], format=operation)
    response = post(http, T + ('/query' if operation == 'query' else '/export'), csrf, body)
    withheld(response, task['id'], source['file_name'])


@pytest.mark.parametrize('operation', ['query', 'csv', 'xlsx'])
def test_new_retained_event_scope_with_unchanged_current_source_withholds_prepared_output(env, monkeypatch, operation):
    from kestrel.models import ReviewTaskEvent
    from kestrel.services import data_tables as tables
    from kestrel.services.auth import clock
    http, sessions, ids, _ = env
    scopes(sessions, ids, [ids['sme']], 'pricing')
    csrf = signed(http)
    _, good = create_task(http, csrf, ids['matter'], ids['lawyer'], 'a-first-page-task')
    source, task = create_task(http, csrf, ids['matter'], ids['lawyer'], 'z-new-retained-secret')
    original = tables.collect if operation == 'query' else tables.selected
    done = False
    def append_after_prepare(db, actor, view, payload):
        nonlocal done
        value = original(db, actor, view, payload)
        if not done:
            done = True
            # Fixture represents a cleared concurrent deadline event captured
            # while pricing-restricted, followed by source relaxation. The final
            # source policy is unchanged; the immutable event alone adds taint.
            with sessions() as writer:
                writer.add(ReviewTaskEvent(matter_id=ids['matter'], source_id=source['id'],
                    retained_classification='clean_team', retained_scope='pricing', task_id=task['id'],
                    revision=2, operation='deadline', from_state='assigned', to_state='assigned',
                    assignee_id=ids['lawyer'], actor_id=ids['sme'], due_at=clock() + 600,
                    rationale='NEW_RETAINED_EVENT_PRIVATE_CANARY', request_key='concurrent-retained-event',
                    input_hash=hashlib.sha256(b'synthetic-concurrent-task-event').hexdigest(), occurred_at=clock()))
                writer.commit()
        return value
    monkeypatch.setattr(tables, 'collect' if operation == 'query' else 'selected', append_after_prepare)
    if operation == 'query':
        body = {'matter_id': ids['matter'], 'length': 1, 'sort': 'file_name'}
    else:
        body = {'matter_id': ids['matter'], 'ids': [good['id'], task['id']], 'format': operation}
    response = post(http, T + ('/query' if operation == 'query' else '/export'), csrf, body)
    withheld(response, task['id'], source['file_name'], 'NEW_RETAINED_EVENT_PRIVATE_CANARY')
    assert response.status_code == 409, response.text


def test_inactive_target_after_picker_result_is_rechecked_without_assigning(env):
    from kestrel.models import Account
    http, sessions, ids, _ = env
    csrf = signed(http)
    _, task = create_task(http, csrf, ids['matter'], ids['lawyer'], 'target-recheck-task')
    payload = command(ids, [task])
    response = post(http, T + '/eligible-people', csrf, {'matter_id': ids['matter'], 'items': payload['items']})
    assert response.status_code == 200 and ids['sme'] in {person['id'] for person in response.json()}
    with sessions() as db:
        db.get(Account, ids['sme']).active = False
        db.commit()
    before = task_counts(sessions, task['id'])
    response = post(http, T + '/bulk-reassign', csrf, payload)
    assert response.status_code == 200 and response.json()['results'] == []
    assert response.json()['unavailable'] == 1 and task['id'] not in response.text
    assert task_counts(sessions, task['id']) == before


def test_freeze_blocks_reassignment_without_consuming_task_history(env):
    from kestrel.models import MatterLifecycle
    http, sessions, ids, _ = env
    csrf = signed(http)
    _, task = create_task(http, csrf, ids['matter'], ids['lawyer'], 'frozen-bulk-task')
    before = task_counts(sessions, task['id'])
    with sessions() as db:
        db.add(MatterLifecycle(matter_id=ids['matter'], frozen=True)); db.commit()
    response = post(http, T + '/bulk-reassign', csrf, command(ids, [task]))
    withheld(response, task['id'])
    assert response.status_code == 409
    assert task_counts(sessions, task['id']) == before
