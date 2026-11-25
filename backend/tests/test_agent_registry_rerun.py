"""The server bridge consumes current SME authority; client IDs grant nothing."""
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_auth_policy import env, login
from test_agent_registry import registry, publish, replacement, run_with_profile, URL, person
from test_document_workflow import candidate
from test_observability_governance import post
from kestrel import models as m
from kestrel.services import ddr_runs


def authorized_impact(registry):
    http, _, ids, _ = registry
    _, finding, _ = candidate(registry)
    original = publish(registry)
    original_run = run_with_profile(registry, [finding['id']], original)
    target = replacement(registry, original)
    token = login(http, 'sme').json()['csrf_token']
    tasks = http.get(URL + '/impacts', params={'matter_id': ids['matter']}).json()
    task = tasks[0]
    response = post(http, URL + '/impacts/' + task['id'] + '/decisions', token, {
        'operation': 'approve', 'snapshot_hash': task['snapshot_hash'], 'target_hash': target['content_hash'],
        'rationale': 'Independent SME authorizes the exact reviewed source scope and replacement agent configuration'})
    assert response.status_code == 200, response.text
    return task, target, original_run, finding, token


def test_explicit_rerun_bridge_is_idempotent_and_revocation_blocks_queued_execution(registry):
    http, sessions, ids, _ = registry
    task, target, original_run, finding, token = authorized_impact(registry)
    path = '/api/v1/ddr/agent-impacts/' + task['id'] + '/rerun'
    command = {'rationale': 'Start the separately authorized synthetic rerun; retain the prior approved history'}
    response = post(http, path, token, command)
    assert response.status_code == 201, response.text
    new_run = response.json()['id']
    assert new_run != original_run
    assert post(http, path, token, command).json()['id'] == new_run
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.DDRRun)) == 2
        assert ddr_runs.execution_authority(db, new_run)[0].id == new_run
        assert db.get(m.DDRExecution, original_run).state == 'queued'
    response = post(http, URL + '/impacts/' + task['id'] + '/decisions', token, {
        'operation': 'revoke', 'snapshot_hash': task['snapshot_hash'], 'target_hash': target['content_hash'],
        'rationale': 'Revoke the scoped reanalysis permission before queued execution begins'})
    assert response.status_code == 200, response.text
    with sessions() as db:
        with pytest.raises(HTTPException): ddr_runs.execution_authority(db, new_run)
        assert db.scalar(select(func.count()).select_from(m.DDRRun)) == 2
    assert post(http, path, token, command).status_code == 403


def test_client_cannot_forge_the_reserved_server_rerun_key(registry):
    http, sessions, ids, _ = registry
    task, target, _, finding, token = authorized_impact(registry)
    response = post(http, '/api/v1/ddr/matters/' + ids['matter'] + '/runs', token, {
        'matter_id': ids['matter'], 'request_key': 'agent-impact-' + task['id'],
        'finding_ids': [finding['id']], 'playbook_id': finding['playbook_id'], 'agent_profile_ids': [target['id']],
        'title': 'Client-supplied spoof of a server-owned impact run', 'audience': 'halden',
        'rationale': 'An arbitrary client request key must not represent governed server authority'})
    assert response.status_code in {403, 422}, response.text
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.DDRRun)) == 1
