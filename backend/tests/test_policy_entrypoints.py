"""Cross-entry-point regressions for canonical document authorization."""
import pytest
from fastapi import HTTPException
from test_auth_policy import env, login
from test_document_abac import document
from test_wall_checker import setup, check
from test_observability_governance import post
from kestrel.models import Account, EthicalWall
from kestrel.repositories.identity import principal
from kestrel.services import documents, policy, workflow
from kestrel.services.auth import clock


@pytest.mark.parametrize('changes,action,expected', [
    ({}, 'read', True),
    ({'quarantined': True}, 'read', False),
    ({'classification_confirmed': False}, 'read', False),
    ({'classification': 'clean_team', 'clean_team_scope': 'pricing'}, 'read', False),
    ({'ai_restricted': True}, 'analyze', False),
    ({'signing_frozen': True}, 'analyze', False),
    ({'superseded': True}, 'read', False),
    ({'superseded': True}, 'historical_read', True),
    ({}, 'share', False),
])
def test_checker_endpoint_and_workflow_share_document_decision(env, changes, action, expected):
    http, sessions, ids, _ = env
    root_csrf = setup(env)
    with sessions() as db:
        row = document(db, ids, **changes)
        db.commit()
        version_id = row.id
        actor = principal(db, db.get(Account, ids['lawyer']), clock())
        decision = policy.evaluate(db, actor, row, action, clock())
        assert decision['allowed'] is expected
        assert documents.evaluate(db, actor, row, action, clock()) == decision
        if expected:
            workflow.require_policy(db, actor, row, action)
        else:
            with pytest.raises(HTTPException) as error:
                workflow.require_policy(db, actor, row, action)
            assert error.value.status_code == 403
    simulated = check(http, root_csrf, action=action, document_version_ids=[version_id])
    assert simulated.status_code == 200, simulated.text
    assert simulated.json()['simulation_only'] is True
    assert simulated.json()['documents'][0]['allowed'] is expected
    csrf = login(http, 'lawyer').json()['csrf_token']
    result = post(http, '/api/v1/document-authorizations', csrf,
                  {'document_version_id': version_id, 'action': action})
    assert result.status_code == 200, result.text
    assert result.json() == decision


def test_precheck_does_not_survive_new_wall(env):
    http, sessions, ids, _ = env
    root_csrf = setup(env)
    with sessions() as db:
        row = document(db, ids)
        db.commit()
        version_id = row.id
    assert check(http, root_csrf, document_version_ids=[version_id]).json()['allowed']
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['lawyer'], matter_id=ids['matter']))
        db.commit()
    csrf = login(http, 'lawyer').json()['csrf_token']
    result = post(http, '/api/v1/document-authorizations', csrf,
                  {'document_version_id': version_id, 'action': 'read'})
    assert result.status_code == 200
    assert not result.json()['allowed']
    with sessions() as db:
        actor = principal(db, db.get(Account, ids['lawyer']), clock())
        with pytest.raises(HTTPException) as error:
            policy.require(db, actor, documents.load(db, version_id), 'read', clock())
        assert error.value.status_code == 403
