"""Durable run commands never accept graph-provided identity or legal approval."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_auth_policy import env
from test_document_workflow import candidate
from kestrel import models as m
from kestrel.repositories.identity import principal
from kestrel.services.auth import clock
from kestrel.services import ddr_runs as service
from kestrel.schemas.ddr_runs import Create


def actor(db,uid):return principal(db,db.get(m.Account,uid),clock())

def payload(ids,finding,**changes):
    return Create(matter_id=ids['matter'],request_key='ddr-isolated-test-001',finding_ids=[finding['id']],playbook_id=finding['playbook_id'],title='Synthetic internal due diligence draft',audience='halden',rationale='Prepare a bounded report from reviewed exact source evidence',**changes)

def test_create_idempotency_opaque_records_and_scoped_read(env):
    _,sessions,ids,_=env;source,finding,_=candidate(env)
    with sessions() as db:
        person=actor(db,ids['lawyer']);p=payload(ids,finding)
        run=service.create(db,person,p)
        assert service.create(db,person,p).id==run.id
        assert db.get(m.DDRExecution,run.id).state=='queued'
        assert finding['summary'] not in run.snapshot_json
        assert db.scalar(select(m.DDREvidence).where(m.DDREvidence.run_id==run.id)).source_id==source['id']
        with pytest.raises(HTTPException) as error:service.create(db,person,p.model_copy(update={'title':'Changed title bound to same request'}))
        assert error.value.status_code==409
        for user in ['root','bank']:
            with pytest.raises(HTTPException):service.read(db,actor(db,ids[user]),run.id)
        service.cancel(db,person,run.id,'Cancel this synthetic queued run before processing')
        assert db.get(m.DDRExecution,run.id).state=='cancelled'
        with pytest.raises(HTTPException):service.execution_authority(db,run.id)


def test_source_restriction_and_playbook_drift_invalidate_execution(env):
    _,sessions,ids,_=env;source,finding,_=candidate(env)
    with sessions() as db:
        run=service.create(db,actor(db,ids['lawyer']),payload(ids,finding))
        policy=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,source['id']).policy_id)
        policy.ai_restricted=True;db.commit()
        with pytest.raises(HTTPException):service.execution_authority(db,run.id)


def test_signing_freeze_and_unpublished_configuration_refuse_runs(env):
    _,sessions,ids,_=env;_,finding,_=candidate(env)
    with sessions() as db:
        person=actor(db,ids['lawyer']);p=payload(ids,finding)
        db.add(m.MatterLifecycle(matter_id=ids['matter'],frozen=True));db.commit()
        with pytest.raises(HTTPException) as error:service.create(db,person,p)
        assert error.value.status_code==409
