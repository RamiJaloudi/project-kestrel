"""Reviewed-only snapshot boundaries for the later graph integration."""
import json
import pytest
from fastapi import HTTPException
from test_auth_policy import env
from test_document_workflow import candidate
from kestrel import models as m
from kestrel.repositories.identity import principal
from kestrel.services.auth import clock
from kestrel.services import ddr_evidence as e


def actor(db,uid):return principal(db,db.get(m.Account,uid),clock())


def test_snapshot_is_opaque_exact_and_rejects_restriction_drift(env):
    _,sessions,ids,_=env;source,finding,_=candidate(env)
    with sessions() as db:
        bundle=e.capture(db,actor(db,ids['lawyer']),ids['matter'],[finding['id']])
        serialized=json.dumps(bundle['snapshot'])
        assert finding['summary'] not in serialized and 'quote' not in bundle['snapshot']['items'][0]
        assert bundle['content'][0]['evidence'][0]['quote']=='change of control'
        assert e.validate(db,actor(db,ids['lawyer']),bundle['snapshot'])['hash']==bundle['hash']
        policy=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,source['id']).policy_id)
        policy.ai_restricted=True;db.commit()
        with pytest.raises(HTTPException) as error:e.validate(db,actor(db,ids['lawyer']),bundle['snapshot'])
        assert error.value.status_code in {403,409}


def test_root_bank_wrong_matter_and_unreviewed_evidence_denied(env):
    _,sessions,ids,_=env;_,finding,_=candidate(env)
    with sessions() as db:
        for uid in [ids['root'],ids['bank']]:
            with pytest.raises(HTTPException):e.capture(db,actor(db,uid),ids['matter'],[finding['id']])
        with pytest.raises(HTTPException):e.capture(db,actor(db,ids['lawyer']),ids['other'],[finding['id']])
        db.get(m.DocumentPolicyVersion,db.get(m.SourceFinding,finding['id']).policy_id).review_state='candidate';db.commit()
        with pytest.raises(HTTPException) as error:e.capture(db,actor(db,ids['lawyer']),ids['matter'],[finding['id']])
        assert error.value.status_code==409


def test_snapshot_rejects_forged_offsets_hash_and_duplicate_inputs(env):
    _,sessions,ids,_=env;_,finding,_=candidate(env)
    with sessions() as db:
        person=actor(db,ids['lawyer']);bundle=e.capture(db,person,ids['matter'],[finding['id']])
        changed=json.loads(json.dumps(bundle['snapshot']));changed['items'][0]['evidence'][0]['start']+=1
        with pytest.raises(HTTPException):e.validate(db,person,changed)
        with pytest.raises(HTTPException):e.capture(db,person,ids['matter'],[finding['id'],finding['id']])
