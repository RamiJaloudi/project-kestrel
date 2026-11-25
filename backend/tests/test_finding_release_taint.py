"""Independent regression: a current ordinary assessment cannot erase prior taint."""
from fastapi.testclient import TestClient
from test_auth_policy import env,login
from test_document_workflow import upload,BASE,allow_processing
from test_diligence import assessment,D
from test_observability_governance import post
from kestrel import models as m
from kestrel.services.auth import clock


def test_prior_restricted_finding_chain_cannot_emit_a_new_unrestricted_release(env):
    h,sessions,ids,app=env
    # Enable only the isolated fixture's normally governed audience-sharing gate;
    # its absence must not mask the retained-chain boundary under examination.
    allow_processing(h,sessions,ids)
    with sessions() as db:
        for uid in [ids['lawyer'],ids['sme']]:db.add(m.CleanTeamMembership(account_id=uid,matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600))
        db.commit()
    c=login(h).json()['csrf_token']
    src=upload(h,c,ids['matter'],classification='clean_team',clean_team_scope='pricing').json()
    assert post(h,BASE+'/documents/'+src['id']+'/confirm',c,{'snapshot_hash':src['snapshot_hash'],'rationale':'Confirm synthetic restricted source before retained assessment'}).status_code==200
    item=post(h,D+'/findings',c,assessment(src,summary='RETAINED_CHAIN_PRIVATE_CANARY requires prior consent.')).json()
    with sessions() as db:
        policy=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,src['id']).policy_id)
        policy.classification='ordinary';policy.clean_team_scope=None;db.commit()
    r=post(h,D+'/findings/'+item['id']+'/revisions',c,assessment(src,expected_revision=1,summary='RETAINED_CHAIN_PRIVATE_CANARY requires prior consent.'))
    assert r.status_code==201,r.text;current=r.json()
    package=post(h,BASE+'/releases',c,{'matter_id':ids['matter'],'audience':'halden','title':'Prior restricted finding summary',
        'summary':'RETAINED_CHAIN_PRIVATE_CANARY requires prior consent.',
        'references':[{'finding_id':item['id'],'revision_id':current['revision_id'],'public_reference':'Synthetic exact contract'}]})
    if package.status_code in {403,409}:return
    assert package.status_code==201,package.text;package=package.json()
    c=login(h,'sme').json()['csrf_token']
    decision=post(h,BASE+'/releases/'+package['id']+'/approve',c,{'content_hash':package['content_hash'],'snapshot_hash':package['snapshot_hash'],'rationale':'Independent fixture package review without any antitrust declassification'})
    if decision.status_code in {403,409}:return
    assert decision.status_code==200,decision.text
    with TestClient(app,base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        response=client.get(BASE+'/releases/'+package['id'])
        assert response.status_code in {403,409},'Prior restricted chain emitted without antitrust handling'
        assert 'RETAINED_CHAIN_PRIVATE_CANARY' not in response.text
