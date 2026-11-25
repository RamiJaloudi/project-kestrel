import pytest
from sqlalchemy import select
from test_auth_policy import env,login
from kestrel.models import DocumentPolicyVersion as Doc,PolicySource,Account,ServiceClient,ServiceToken
from kestrel.repositories.identity import principal
from kestrel.services.auth import clock,HASHER,digest
from kestrel.services.documents import snapshot,load
from kestrel.services.policy import evaluate


def document(db,ids,**kwargs):
    values=dict(matter_id=ids['matter'],document_id='synthetic-source',source_hash='a'*64,
                resource_type='contract',classification='ordinary',classification_confirmed=True,review_state='reviewed')
    values.update(kwargs)
    row=Doc(**values);db.add(row);db.flush();return row


@pytest.mark.parametrize('changes,action,reason',[
 ({'quarantined':True},'read','QUARANTINED'),
 ({'classification_confirmed':False},'read','CLASSIFICATION_PENDING'),
 ({'classification':'unknown'},'read','UNCLASSIFIED'),
 ({'resource_type':'unknown'},'read','UNCLASSIFIED'),
 ({'ai_restricted':True},'analyze','AI_RESTRICTED'),
 ({'signing_frozen':True},'analyze','SIGNING_FROZEN'),
 ({'superseded':True},'read','SUPERSEDED'),
 ({},'edit','NEW_VERSION_REQUIRED')])
def test_type_state_denials(env,changes,action,reason):
    _,sessions,ids,_=env
    with sessions() as db:
        actor=principal(db,db.get(Account,ids['lawyer']),clock())
        doc=document(db,ids,**changes)
        assert evaluate(db,actor,doc,action,clock())['reason_code']==reason


def test_frozen_read_and_historical_not_root_content(env):
    _,sessions,ids,_=env
    with sessions() as db:
        doc=document(db,ids,signing_frozen=True)
        actor=principal(db,db.get(Account,ids['lawyer']),clock())
        assert evaluate(db,actor,doc,'read',clock())['allowed']
        doc.superseded=True
        assert evaluate(db,actor,doc,'historical_read',clock())['allowed']
        root=principal(db,db.get(Account,ids['root']),clock())
        assert not evaluate(db,root,doc,'historical_read',clock())['allowed']


def test_package_approval_binds_sources_and_bank_privilege(env):
    _,sessions,ids,_=env
    with sessions() as db:
        bank=principal(db,db.get(Account,ids['bank']),clock())
        source=document(db,ids)
        report=document(db,ids,resource_type='report',released=True,audience='castlegate')
        db.add(PolicySource(artifact_id=report.id,source_id=source.id));db.flush()
        assert not evaluate(db,bank,report,'download',clock())['allowed']
        report.approved_snapshot_hash=snapshot(db,report)
        assert evaluate(db,bank,report,'download',clock())['allowed']
        source.source_hash='b'*64
        assert evaluate(db,bank,report,'download',clock())['reason_code']=='PACKAGE_CHANGED'
        source.classification='privileged';report.sanitized=True
        report.approved_snapshot_hash=snapshot(db,report)
        assert evaluate(db,bank,report,'read',clock())['reason_code']=='BANK_PRIVILEGE'


def test_cross_matter_lineage_and_clean_team(env):
    _,sessions,ids,_=env
    with sessions() as db:
        actor=principal(db,db.get(Account,ids['lawyer']),clock())
        restricted=document(db,ids,classification='clean_team',clean_team_scope='pricing')
        assert evaluate(db,actor,restricted,'read',clock())['reason_code']=='CLEAN_TEAM_REQUIRED'
        other=document(db,ids,matter_id=ids['other'])
        db.add(PolicySource(artifact_id=restricted.id,source_id=other.id));db.flush()
        assert evaluate(db,actor,restricted,'read',clock())['reason_code']=='LINEAGE_INVALID'


def test_compatibility_batch_contract_and_oauth_scopes(env):
    http,sessions,ids,_=env
    with sessions() as db:
        db.get(Account,ids['lawyer']).email='lawyer@synthetic.example'
        db.add(ServiceClient(client_name='synthetic-service',account_id=ids['lawyer'],
               scopes='ClientMatter.Validate Documents.Authorize',secret_hash=HASHER.hash('test-only-client-secret-32-characters')))
        clientid=db.scalar(select(__import__('kestrel.models',fromlist=['MatterValidation']).MatterValidation.client_id))
        db.commit()
    issued=http.post('/oauth/token',data={'grant_type':'client_credentials'},auth=('synthetic-service','test-only-client-secret-32-characters'))
    assert issued.status_code==200
    token=issued.json()['access_token'];headers={'authorization':'Bearer '+token}
    with sessions() as db:
        assert db.scalar(select(ServiceToken)).token_hash==digest(token)
    pair={'clientId':clientid,'matterId':ids['matter']}
    result=http.post('/api/client-matter-validations',json=pair,headers=headers)
    assert result.status_code==200 and result.json()['valid']
    assert not result.json()['workspaceAllowed']
    batch=http.post('/api/client-matter-validations/batch',json=[pair,{**pair,'matterId':'unknown'}],headers=headers)
    assert [row['valid'] for row in batch.json()]==[True,False]
    assert http.post('/api/ethical-walls',json={**pair,'emails':['lawyer@synthetic.example']},headers=headers).status_code==403
    with sessions() as db:
        db.scalar(select(ServiceClient)).active=False;db.commit()
    assert http.post('/api/client-matter-validations',json=pair,headers=headers).status_code==401


def test_document_api_cannot_accept_forged_attributes(env):
    http,sessions,ids,_=env
    csrf=login(http).json()['csrf_token']
    headers={'origin':'https://firm.localhost','x-csrf-token':csrf}
    with sessions() as db:
        doc=document(db,ids,quarantined=True);db.commit();version=doc.id
    payload={'document_version_id':version,'action':'read'}
    result=http.post('/api/v1/document-authorizations',json=payload,headers=headers)
    assert result.json()['reason_code']=='QUARANTINED'
    assert http.post('/api/v1/document-authorizations',json={**payload,'quarantined':False},headers=headers).status_code==422
