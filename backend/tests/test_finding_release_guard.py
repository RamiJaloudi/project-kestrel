"""Bound source identity and pinned-prefix restriction checks, without retagging artifacts."""
import json
import pytest
from sqlalchemy import select
from test_auth_policy import env
from test_finding_tables import findings
from test_document_workflow import BASE,upload
from test_diligence import D,assessment
from test_observability_governance import post
from kestrel import models as m
from kestrel.services import finding_release_guard as guard
from kestrel.adapters.extraction import canonical


def package(env):
    http,sessions,ids,_=env;source,items,csrf=findings(env);first=items[0]
    response=post(http,D+'/findings/'+first['id']+'/revisions',csrf,assessment(source,expected_revision=1))
    assert response.status_code==201,response.text;last=response.json()
    response=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Ordinary pinned-prefix fixture',
        'summary':'An ordinary corrected finding retains its exact original-source reference.',
        'references':[{'finding_id':first['id'],'revision_id':last['revision_id'],'public_reference':'Synthetic original contract'}]})
    assert response.status_code==201,response.text
    return source,first,last,response.json(),csrf


@pytest.mark.parametrize('dimension',['privilege_not_replaced_by_clean_team','different_scope','ai_restricted','quarantined'])
def test_each_retained_restriction_is_independent_and_source_bound(env,dimension):
    _,sessions,_,_=env;source,first,last,artifact,_=package(env)
    with sessions() as db:
        prior=db.get(m.DocumentPolicyVersion,db.get(m.LegalFindingRevision,first['revision_id']).policy_id)
        current=db.get(m.DocumentPolicyVersion,db.get(m.LegalFindingRevision,last['revision_id']).policy_id)
        if dimension=='privilege_not_replaced_by_clean_team':prior.classification='privileged';current.classification='clean_team';current.clean_team_scope='pricing'
        elif dimension=='different_scope':prior.classification='clean_team';prior.clean_team_scope='pricing';current.classification='clean_team';current.clean_team_scope='strategy'
        else:setattr(prior,dimension,True)
        db.commit();root=db.get(m.DocumentPolicyVersion,db.get(m.ReleasePackage,artifact['id']).policy_id)
        assert guard.denial(db,root)==guard.REASON


def test_unrelated_source_with_same_clean_scope_cannot_cover_original_source(env):
    http,sessions,ids,_=env;source,first,last,artifact,csrf=package(env)
    unrelated=upload(http,csrf,ids['matter'],logical_key='UNRELATED-COVERAGE',file_name='unrelated.txt').json()
    with sessions() as db:
        prior=db.get(m.DocumentPolicyVersion,db.get(m.LegalFindingRevision,first['revision_id']).policy_id)
        prior.classification='clean_team';prior.clean_team_scope='pricing'
        other=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,unrelated['id']).policy_id)
        other.classification='clean_team';other.clean_team_scope='pricing'
        root=db.get(m.DocumentPolicyVersion,db.get(m.ReleasePackage,artifact['id']).policy_id)
        db.add(m.PolicySource(artifact_id=root.id,source_id=other.id));db.commit()
        assert guard.denial(db,root)==guard.REASON


@pytest.mark.parametrize('covered',[False,True])
def test_named_recipient_restriction_cannot_be_dropped(env,covered):
    _,sessions,ids,_=env;_,first,_,artifact,_=package(env)
    with sessions() as db:
        prior=db.get(m.LegalFindingRevision,first['revision_id'])
        root=db.get(m.DocumentPolicyVersion,db.get(m.ReleasePackage,artifact['id']).policy_id)
        db.add(m.PolicyRecipient(policy_id=prior.policy_id,account_id=ids['client']))
        if covered:db.add(m.PolicyRecipient(policy_id=root.id,account_id=ids['client']))
        db.commit()
        assert guard.denial(db,root)==(None if covered else guard.REASON)


def test_future_revision_is_not_added_to_historical_pinned_prefix(env):
    _,sessions,ids,_=env;source,first,last,artifact,_=package(env)
    with sessions() as db:
        release=db.get(m.ReleasePackage,artifact['id']);receipt=(release.content_hash,release.references_json)
        previous=db.get(m.LegalFindingRevision,last['revision_id'])
        future_policy=m.DocumentPolicyVersion(matter_id=ids['matter'],document_id='future-only-restriction',source_hash='a'*64,
            resource_type='finding',classification='clean_team',classification_confirmed=True,review_state='reviewed',clean_team_scope='future-only')
        db.add(future_policy);db.flush()
        db.add(m.PolicySource(artifact_id=future_policy.id,source_id=db.get(m.SourceVersion,source['id']).policy_id))
        values={c.name:getattr(previous,c.name) for c in m.LegalFindingRevision.__table__.columns if c.name not in {'id','version_number','previous_id','policy_id'}}
        db.add(m.LegalFindingRevision(**values,version_number=3,previous_id=previous.id,policy_id=future_policy.id))
        db.get(m.DocumentPolicyVersion,previous.policy_id).superseded=True;db.commit()
        assert guard.denial(db,db.get(m.DocumentPolicyVersion,release.policy_id)) is None
        assert (release.content_hash,release.references_json)==receipt


def test_original_source_node_without_actual_pinned_finding_node_is_insufficient(env):
    _,sessions,ids,_=env;source,_,last,_,_=package(env)
    with sessions() as db:
        root=m.DocumentPolicyVersion(matter_id=ids['matter'],document_id='missing-finding-node',source_hash='b'*64,
            resource_type='report',classification='ordinary',classification_confirmed=True,review_state='reviewed',audience='halden')
        db.add(root);db.flush();db.add(m.PolicySource(artifact_id=root.id,source_id=db.get(m.SourceVersion,source['id']).policy_id))
        db.add(m.ReleasePackage(policy_id=root.id,created_by=ids['lawyer'],title='Exact-node negative fixture',summary='A source node alone cannot prove which assessment was approved.',
            references_json=canonical([{'finding_id':last['id'],'revision_id':last['revision_id'],'public_reference':'Synthetic exact source'}]),content_hash='b'*64,created_at=1))
        db.commit();assert guard.denial(db,root)==guard.REASON
