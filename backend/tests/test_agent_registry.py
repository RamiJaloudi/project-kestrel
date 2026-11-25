"""Synthetic, isolated governance/impact tests; no provider call or live approval."""
import json
import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env, login
from test_document_workflow import BASE, candidate, upload
from test_observability_governance import post
from kestrel import models as m
from kestrel.repositories.identity import principal
from kestrel.services.auth import clock
from kestrel.services import agent_registry as service

URL = '/api/v1/agent-registry'


@pytest.fixture
def registry(env):
    http, _, _, app = env
    from kestrel.api.agent_registry import router
    if not any(getattr(route, 'path', '') == URL for route in app.routes): app.include_router(router)
    return env


def definition(**changes):
    return {'agent_kind': 'contracts', 'provider': 'offline', 'model': 'deterministic-reviewed-v1',
        'prompt': 'Use only supplied reviewed findings with exact citations and preserve approved severity.',
        'tools': ['validate_current_scope', 'read_reviewed_findings', 'read_exact_evidence', 'validate_citations'], **changes}


def body(ids, **changes):
    return {'matter_id': ids['matter'], 'name': 'Synthetic governed contracts agent', 'definition': definition(),
        'rationale': 'Private synthetic configuration for independent legal and technical review',
        'request_key': uuid.uuid4().hex, **changes}


def action(http, csrf, version, operation, **changes):
    return post(http, URL + '/versions/' + version['id'] + '/actions', csrf, {'operation': operation,
        'content_hash': version['content_hash'], 'rationale': 'Fixture reviewer explicitly checks the exact immutable configuration',
        'content_reviewed': operation == 'approve', **changes})


def publish(registry, version=None):
    http, _, ids, _ = registry
    root = login(http, 'root').json()['csrf_token']
    if version is None:
        response = post(http, URL, root, body(ids)); assert response.status_code == 201, response.text
        version = response.json()
    assert action(http, root, version, 'test').status_code == 200
    assert action(http, root, version, 'submit').status_code == 200
    token = login(http, 'sme').json()['csrf_token']
    response = action(http, token, version, 'approve'); assert response.status_code == 200, response.text
    root = login(http, 'root').json()['csrf_token']
    response = action(http, root, version, 'publish'); assert response.status_code == 200, response.text
    return response.json()


def replacement(registry, prior):
    http, _, _, _ = registry
    root = login(http, 'root').json()['csrf_token']
    response = post(http, URL + '/profiles/' + prior['profile_id'] + '/versions', root, {
        'definition': definition(prompt='Retain reviewed conditions and exceptions. Use exact original-language citations and preserve severity.'),
        'rationale': 'Material revised instruction requires independent legal review and scoped impact decisions',
        'request_key': uuid.uuid4().hex, 'expected_version_hash': prior['content_hash']})
    assert response.status_code == 201, response.text
    return publish(registry, response.json())


def person(db, uid):
    return principal(db, db.get(m.Account, uid), clock())


def run_with_profile(registry, finding_ids, profile):
    _, sessions, ids, _ = registry
    from kestrel.schemas.ddr_runs import Create
    from kestrel.services.ddr_runs import create
    with sessions() as db:
        first, _ = __import__('kestrel.services.diligence', fromlist=['resolve']).resolve(db, person(db, ids['lawyer']), finding_ids[0])
        run = create(db, person(db, ids['lawyer']), Create(matter_id=ids['matter'], request_key=uuid.uuid4().hex,
            finding_ids=finding_ids, playbook_id=first.playbook_id, agent_profile_ids=[profile['id']],
            title='Synthetic governed report run', audience='halden', rationale='Retain reviewed evidence for the profile change regression'))
        return run.id


def test_server_manifests_budget_bounds_and_root_cannot_self_approve(registry):
    http, sessions, ids, app = registry
    root = login(http, 'root').json()['csrf_token']
    for changes in [{'tools': ['release_report']}, {'tools': ['grant_access']}, {'provider': 'offline', 'model': 'unknown'},
                    {'max_model_calls': 99}, {'max_cost_cents': 201}, {'max_concurrency': 20}, {'timeout_seconds': 3600},
                    {'base_url': 'https://unapproved.example'}]:
        assert post(http, URL, root, body(ids, definition=definition(**changes))).status_code == 422
    response = post(http, URL, root, body(ids)); assert response.status_code == 201, response.text
    version = response.json()
    assert action(http, root, version, 'publish').status_code == 409
    assert action(http, root, version, 'test').status_code == 200
    assert action(http, root, version, 'submit').status_code == 200
    with sessions() as db:
        role = db.scalar(select(m.Role.id).where(m.Role.name == 'legal_sme'))
        db.add(m.RoleGrant(account_id=ids['root'], role_id=role)); db.commit()
    assert action(http, root, version, 'approve').status_code == 403
    with TestClient(app, base_url='https://bank.localhost') as bank:
        token = login(bank, 'bank', origin='https://bank.localhost').json()['csrf_token']
        response = bank.get(URL, params={'matter_id': ids['matter']}); assert response.status_code == 403
        assert version['id'] not in response.text
    assert post(http, URL, root, body(ids, matter_id=ids['other'])).status_code == 403


def test_exact_test_submission_review_and_immutable_revision_history(registry):
    http, sessions, ids, _ = registry
    root = login(http, 'root').json()['csrf_token']
    payload = body(ids)
    version = post(http, URL, root, payload).json()
    assert post(http, URL, root, payload).json()['id'] == version['id']
    assert action(http, root, version, 'submit').status_code == 409
    assert action(http, root, version, 'test').status_code == 200
    assert action(http, root, version, 'submit').status_code == 200
    token = login(http, 'sme').json()['csrf_token']
    assert action(http, token, version, 'approve', content_hash='0' * 64).status_code == 409
    assert action(http, token, version, 'approve', content_reviewed=False).status_code == 422
    assert action(http, token, version, 'approve').status_code == 200
    root = login(http, 'root').json()['csrf_token']
    assert action(http, root, version, 'publish').status_code == 200
    revised = replacement(registry, version)
    assert revised['revision'] == 2 and revised['content_hash'] != version['content_hash']
    response = http.get(URL + '/diff', params={'from_id': version['id'], 'to_id': revised['id']})
    assert response.status_code == 200 and any(change['path'] == '/prompt' for change in response.json()['changes'])
    with sessions() as db:
        assert db.get(m.AgentProfileVersion, version['id']).content_hash == version['content_hash']
        with pytest.raises(DBAPIError):
            db.execute(text('UPDATE agent_profile_versions SET definition_json=:value WHERE id=:id'), {'value': '{}', 'id': version['id']}); db.commit()


def test_revoked_approver_and_replaced_new_run_config_fail_closed(registry):
    _, sessions, ids, _ = registry
    original = publish(registry)
    revised = replacement(registry, original)
    with sessions() as db:
        actor = person(db, ids['lawyer'])
        with pytest.raises(HTTPException) as error: service.resolve_versions(db, actor, [original['id']])
        assert error.value.status_code == 409
        assert service.resolve_versions(db, actor, [original['id']], for_new_run=False)['agent_profile_ids'] == [original['id']]
        db.add(m.EthicalWall(account_id=ids['sme'], matter_id=ids['matter'], active=True)); db.commit()
        with pytest.raises(HTTPException) as error: service.resolve_versions(db, actor, [revised['id']])
        assert error.value.status_code == 403


def test_material_publication_creates_scoped_inbox_without_jobs_and_ack_is_not_approval(registry):
    http, sessions, ids, _ = registry
    _, finding, _ = candidate(registry)
    original = publish(registry)
    run_id = run_with_profile(registry, [finding['id']], original)
    revised = replacement(registry, original)
    token = login(http, 'sme').json()['csrf_token']
    response = http.get(URL + '/impacts', params={'matter_id': ids['matter']}); assert response.status_code == 200, response.text
    tasks = response.json(); assert len(tasks) == 1
    task = tasks[0]; assert task['run_id'] == run_id and task['state'] == 'awaiting_sme' and not task['stale']
    assert any(change['path'] == '/prompt' for change in task['diff'])
    response = post(http, URL + '/impacts/' + task['id'] + '/notification', token, {'operation': 'acknowledge'})
    assert response.status_code == 200 and response.json()['notification']['acknowledged']
    assert response.json()['state'] == 'awaiting_sme'
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.DDRRun)) == 1
        assert db.get(m.DDRExecution, run_id).state == 'queued'
        with pytest.raises(HTTPException): service.authorize_rerun(db, person(db, ids['sme']), task['id'])
    payload = {'operation': 'approve', 'snapshot_hash': task['snapshot_hash'], 'target_hash': revised['content_hash'],
        'rationale': 'Independent SME explicitly authorizes a new scoped run from this exact impact'}
    assert post(http, URL + '/impacts/' + task['id'] + '/decisions', token, {**payload, 'snapshot_hash': '0' * 64}).status_code == 409
    response = post(http, URL + '/impacts/' + task['id'] + '/decisions', token, payload)
    assert response.status_code == 200 and response.json()['state'] == 'approved', response.text
    with sessions() as db:
        contract = service.authorize_rerun(db, person(db, ids['sme']), task['id'])
        assert contract['original_run_id'] == run_id and contract['agent_profile_ids'] == [revised['id']]
        assert contract['finding_ids'] == [finding['id']] and len(contract['authorization_hash']) == 64
        assert db.scalar(select(func.count()).select_from(m.DDRRun)) == 1
        notification = db.scalar(select(m.AgentProfileImpactNotification))
        with pytest.raises(DBAPIError):
            db.execute(text('UPDATE agent_profile_impact_notifications SET account_id=:uid WHERE id=:id'), {'uid': ids['lawyer'], 'id': notification.id}); db.commit()
    with sessions() as db:
        db.add(m.MatterLifecycle(matter_id=ids['matter'], frozen=True)); db.commit()
    assert post(http, URL + '/impacts/' + task['id'] + '/notification', token, {'operation': 'read'}).status_code == 200
    response = post(http, URL + '/impacts/' + task['id'] + '/decisions', token, {**payload, 'operation': 'revoke'})
    assert response.status_code == 200 and response.json()['state'] == 'revoked', response.text
    root = login(http, 'root').json()['csrf_token']
    assert action(http, root, revised, 'archive').status_code == 200


def test_mixed_source_impact_union_blocks_uncleared_inbox_decisions_and_rerun(registry):
    http, sessions, ids, _ = registry
    _, first, _ = candidate(registry)
    with sessions() as db:
        for uid in [ids['lawyer'], ids['sme']]: db.add(m.CleanTeamMembership(account_id=uid, matter_id=ids['matter'], scope='pricing', approved_by=ids['root'], expires_at=clock() + 3600))
        db.commit()
    token = login(http).json()['csrf_token']
    response = upload(http, token, ids['matter'], logical_key='AGENT-PRICING', file_name='restricted-agent-source.txt', classification='clean_team', clean_team_scope='pricing')
    assert response.status_code == 201, response.text
    source = response.json()
    assert post(http, BASE + '/documents/' + source['id'] + '/confirm', token, {'snapshot_hash': source['snapshot_hash'], 'rationale': 'Confirm synthetic clean-team evidence'}).status_code == 200
    token = login(http, 'sme').json()['csrf_token']
    response = post(http, '/api/v1/jobs', token, {'playbook_id': first['playbook_id'], 'document_version_id': source['id'], 'idempotency_key': 'agent-clean-fixture-001', 'rationale': 'Run the approved offline synthetic evidence extractor'})
    assert response.status_code == 201, response.text
    from kestrel.services import jobs
    assert jobs.run_once(sessions)
    with sessions() as db: second_id = db.scalar(select(m.SourceFinding.id).where(m.SourceFinding.source_id == source['id']))
    token = login(http).json()['csrf_token']
    response = post(http, BASE + '/findings/' + second_id + '/review', token, {'decision': 'reviewed', 'rationale': 'Attorney reviewed the exact synthetic restricted source passage'})
    assert response.status_code == 200, response.text
    original = publish(registry)
    run_with_profile(registry, [first['id'], second_id], original)
    replacement(registry, original)
    login(http, 'sme')
    task = http.get(URL + '/impacts', params={'matter_id': ids['matter']}).json()[0]
    with sessions() as db:
        assert len(service.audit_records(db, task['id'])) == 2
        role = db.scalar(select(m.Role).where(m.Role.name == 'matter_auditor'))
        if role is None:
            role = m.Role(name='matter_auditor'); db.add(role); db.flush()
        db.add(m.RoleGrant(account_id=ids['sme'], role_id=role.id)); db.commit()
        from kestrel.services import auditing
        assert any(row['object_id'] == task['id'] for row in auditing.selected(db, person(db, ids['sme']), 'legal_sme', ids['matter']))
        db.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id == ids['sme'])).revoked = True; db.commit()
    assert http.get(URL + '/impacts', params={'matter_id': ids['matter']}).json() == []
    with sessions() as db:
        with pytest.raises(HTTPException): service.task_read(db, person(db, ids['sme']), task['id'])
        with pytest.raises(HTTPException): service.authorize_rerun(db, person(db, ids['sme']), task['id'])
        with pytest.raises(HTTPException): service.task_read(db, person(db, ids['root']), task['id'])
        assert all(row['object_id'] != task['id'] for row in auditing.selected(db, person(db, ids['sme']), 'legal_sme', ids['matter']))


def test_migration_retains_all_tables_when_downgrade_is_refused(registry):
    http, sessions, ids, _ = registry
    root = login(http, 'root').json()['csrf_token']
    assert post(http, URL, root, body(ids)).status_code == 201
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    with pytest.raises(RuntimeError, match='Retained agent governance'):
        command.downgrade(Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini')), '0036')
    with sessions() as db:
        names = set(inspect(db.bind).get_table_names())
        assert {model.__tablename__ for model in [m.AgentProfile, m.AgentProfileVersion, m.AgentProfileEvent,
            m.AgentProfileReplacement, m.AgentProfileImpact, m.AgentProfileImpactItem, m.AgentProfileImpactTask,
            m.AgentProfileImpactDecision, m.AgentProfileImpactNotification]} <= names
        assert db.scalar(select(func.count()).select_from(m.AgentProfile)) == 1


def test_runtime_configuration_honors_lower_profile_ceilings_and_required_tool_manifest(registry):
    http, sessions, ids, _ = registry
    _, finding, _ = candidate(registry)
    root = login(http, 'root').json()['csrf_token']
    response = post(http, URL, root, body(ids, definition=definition(total_tokens=9000,
        max_output_tokens=800, max_concurrency=1, max_cost_cents=100, timeout_seconds=10)))
    assert response.status_code == 201, response.text
    version = publish(registry, response.json())
    from kestrel.services.ddr_runs import configuration
    with sessions() as db:
        value, _ = configuration(db, person(db, ids['lawyer']), ids['matter'], finding['playbook_id'], 'offline', [version['id']])
        assert value['total_tokens'] == 9000 and value['max_output_tokens'] == 800
        assert value['max_concurrency'] == 1 and value['max_cost_cents'] == 100
    root = login(http, 'root').json()['csrf_token']
    response = post(http, URL + '/profiles/' + version['profile_id'] + '/versions', root, {
        'definition': definition(tools=['read_reviewed_findings']), 'expected_version_hash': version['content_hash'],
        'rationale': 'A manifest without required exact-evidence tools must be rejected by the runtime',
        'request_key': uuid.uuid4().hex})
    assert response.status_code == 201, response.text
    unusable = publish(registry, response.json())
    with sessions() as db:
        with pytest.raises(HTTPException) as error:
            configuration(db, person(db, ids['lawyer']), ids['matter'], finding['playbook_id'], 'offline', [unusable['id']])
        assert error.value.status_code == 422
