import json
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_document_workflow import candidate,upload,BASE,TEXT
from test_observability_governance import post

D='/api/v1/diligence'
def assessment(source,**changes):
    return {'source_id':source['id'],'expected_revision':0,'decision':'reviewed',
        'summary':'Consent requires transaction-specific follow-up before signing.','topic':'change_of_control',
        'severity':'high','materiality':'material','exposure':'consent','workflow_status':'open',
        'action':'Obtain counsel confirmation and prepare a consent request.','owner_id':None,'due_on':None,
        'rationale':'Lawyer checked the clause in the full source context.',
        'evidence':[{'unit':1,'quote':'change of control'}],**changes}

def test_correction_is_versioned_updates_registers_and_invalidates_old_release(env):
    http,sessions,ids,_=env;source,finding,csrf=candidate(env)
    draft=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Original reviewed note',
        'summary':'Original reviewed consent note for the synthetic customer contract.',
        'references':[{'finding_id':finding['id'],'public_reference':'Customer agreement'}]}).json()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+draft['id']+'/approve',csrf,{'content_hash':draft['content_hash'],'snapshot_hash':draft['snapshot_hash'],'rationale':'Independent review of original package'}).status_code==200
    csrf=login(http,'lawyer').json()['csrf_token']
    body=assessment(source)
    result=post(http,D+'/findings/'+finding['id']+'/revisions',csrf,body)
    assert result.status_code==201,result.text
    revised=result.json();assert revised['revision']==1 and revised['summary']==body['summary']
    assert revised['origin']=='ai_candidate' and revised['original_summary']==finding['summary']
    assert post(http,D+'/findings/'+finding['id']+'/revisions',csrf,body).status_code==409
    rows=http.get(BASE+'/findings',params={'matter_id':ids['matter']}).json()
    assert rows[0]['revision_id']==revised['revision_id']
    board=http.get(D+'/board',params={'matter_id':ids['matter']}).json()
    assert board['metrics']['material_open_risks']==1 and board['metrics']['fully_reviewed']==0
    assert board['consents'][0]['exposure']=='consent'
    # Original bytes and release summary are retained, while old external eligibility is removed.
    from fastapi.testclient import TestClient
    with TestClient(env[3],base_url='https://client.localhost') as external:
        login(external,'client',origin='https://client.localhost')
        assert external.get(BASE+'/releases/'+draft['id']).status_code==403
    stale=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'Stale draft attempt','summary':'This UI used an earlier finding version.',
        'references':[{'finding_id':finding['id'],'public_reference':'Customer contract','revision_id':finding['id']}]})
    assert stale.status_code==409
    fresh=post(http,BASE+'/releases',csrf,{'matter_id':ids['matter'],'audience':'halden','title':'New corrected release','summary':'A new summary independently approved against the corrected finding.',
        'references':[{'finding_id':finding['id'],'public_reference':'Customer contract','revision_id':revised['revision_id']}]})
    assert fresh.status_code==201,fresh.text
    release=fresh.json();csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+release['id']+'/approve',csrf,{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],'rationale':'Independent approval of corrected finding version'}).status_code==200
    with TestClient(env[3],base_url='https://client.localhost') as external:
        login(external,'client',origin='https://client.localhost')
        assert external.get(BASE+'/releases/'+release['id']).status_code==200
    login(http,'lawyer')
    history=http.get(D+'/findings/'+finding['id']+'/history').json()
    assert len(history)==2 and history[0]['summary']==finding['summary']
    with sessions() as db:
        assert db.execute(text('SELECT summary FROM release_packages WHERE id=:id'),{'id':draft['id']}).scalar()==draft['summary']
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE legal_finding_revisions SET summary='silent edit'"));db.commit()
        db.rollback()

def test_manual_finding_full_review_and_scope_denials(env):
    http,sessions,ids,_=env;csrf=login(http,'lawyer').json()['csrf_token']
    source=upload(http,csrf,ids['matter']).json()
    assert post(http,BASE+'/documents/'+source['id']+'/confirm',csrf,{'snapshot_hash':source['snapshot_hash'],'rationale':'Confirm intake for human-only review'}).status_code==200
    from kestrel.models import DocumentPolicyVersion
    with sessions() as db:
        db.get(DocumentPolicyVersion,db.execute(text('SELECT policy_id FROM source_versions WHERE id=:id'),{'id':source['id']}).scalar()).ai_restricted=True;db.commit()
    result=post(http,D+'/findings',csrf,assessment(source))
    assert result.status_code==201,result.text
    manual=result.json();assert manual['origin']=='lawyer' and manual['review_state']=='reviewed'
    profile={'expected_revision':0,'title':'Synthetic customer agreement','counterparty':'Orion Demo AG','scope':'customer','coverage_state':'complete','rationale':'Human reviewed the whole document and all outstanding candidates.'}
    assert post(http,D+'/documents/'+source['id']+'/reviews',csrf,profile).status_code==201
    board=http.get(D+'/board',params={'matter_id':ids['matter']}).json()
    assert board['metrics']['received']==1 and board['metrics']['fully_reviewed'] is None
    assert board['review_metrics_withheld'] is True
    assert board['contracts'][0]['counterparty']==''
    assert board['contracts'][0]['document_review']['metadata_withheld'] is True
    # No historical handling receipt is invented, and the retained row is unchanged.
    from kestrel.models import DocumentReviewVersion
    from sqlalchemy import select
    with sessions() as db:
        retained=db.scalar(select(DocumentReviewVersion).where(DocumentReviewVersion.source_id==source['id']))
        assert retained.counterparty=='Orion Demo AG' and retained.coverage_state=='complete'
    assert board['metrics']['analyzed']==0  # manual review is not an AI run
    assert post(http,D+'/findings',csrf,assessment(source,evidence=[{'unit':1,'quote':'Fabricated clause'}])).status_code==422
    assert post(http,D+'/findings',csrf,assessment(source,owner_id=ids['root'])).status_code==422
    login(http,'root');assert http.get(D+'/board',params={'matter_id':ids['matter']}).status_code==403
    csrf=login(http,'root').json()['csrf_token'];assert post(http,D+'/findings',csrf,assessment(source)).status_code==403

def test_partial_findings_do_not_imply_whole_document_review(env):
    http,_,ids,_=env;source,finding,csrf=candidate(env)
    board=http.get(D+'/board',params={'matter_id':ids['matter']}).json()
    assert board['metrics']['analyzed'] is None and board['analysis_metrics_withheld'] is True and board['metrics']['fully_reviewed']==0
    assert board['metrics']['unassessed_findings']>=1
    # A rejection is a retained new decision, excluded from active risk/consent registers.
    decision=post(http,D+'/findings/'+finding['id']+'/revisions',csrf,assessment(source,decision='rejected',severity='information',materiality='not_material',exposure='none'))
    assert decision.status_code==201,decision.text
    board=http.get(D+'/board',params={'matter_id':ids['matter']}).json()
    assert not board['risks'] and not board['consents']

def test_register_does_not_disclose_clean_team_or_other_matters(env):
    from kestrel.models import CleanTeamMembership
    from kestrel.services.auth import clock
    http,sessions,ids,_=env
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+1000));db.commit()
    csrf=login(http,'lawyer').json()['csrf_token']
    source=upload(http,csrf,ids['matter'],classification='clean_team',clean_team_scope='pricing').json()
    assert post(http,BASE+'/documents/'+source['id']+'/confirm',csrf,{'snapshot_hash':source['snapshot_hash'],'rationale':'Confirm restricted original handling'}).status_code==200
    item=post(http,D+'/findings',csrf,assessment(source)).json()
    login(http,'sme')
    board=http.get(D+'/board',params={'matter_id':ids['matter']}).json()
    assert board['metrics']['received']==0 and board['risks']==[] and board['sources']==[]
    assert http.get(D+'/findings/'+item['id']+'/history').status_code==403
    assert http.get(D+'/board',params={'matter_id':ids['other']}).status_code==403


def test_connected_review_progress_separates_analysis_decisions_and_signoff(env):
    http,_,ids,_=env
    source,finding,csrf=candidate(env)
    result=http.get(D+'/board',params={'matter_id':ids['matter']})
    assert result.status_code==200
    progress=result.json()['sources'][0]
    assert progress['id']==source['id']
    assert progress['analysis']['has_completed_run'] is None
    assert progress['analysis']['engine'] is None and progress['analysis']['metadata_withheld'] is True
    assert progress['finding_progress']['reviewed']>=1
    assert progress['document_review']['coverage_state']=='not_started'
    # A reviewed candidate does not silently sign off the entire source.
    assert result.json()['metrics']['fully_reviewed']==0
    payload={'expected_revision':0,'title':'Synthetic complete contract review','counterparty':'Synthetic counterparty',
        'scope':'customer','coverage_state':'complete','rationale':'Lawyer read the whole source and checked all candidate decisions.'}
    saved=post(http,D+'/documents/'+source['id']+'/reviews',csrf,payload)
    assert saved.status_code==201,saved.text
    board=http.get(D+'/board',params={'matter_id':ids['matter']}).json()
    current=board['sources'][0]
    assert current['analysis']['has_completed_run'] is None
    assert current['document_review']['coverage_state']=='unavailable' and current['document_review']['metadata_withheld'] is True
    assert current['document_review']['revision']==1
    assert board['metrics']['fully_reviewed'] is None and board['review_metrics_withheld'] is True
    # The same board never becomes a source-data API for an external audience.
    from fastapi.testclient import TestClient
    with TestClient(env[3],base_url='https://client.localhost') as external:
        login(external,'client',origin='https://client.localhost')
        assert external.get(D+'/board',params={'matter_id':ids['matter']}).status_code==403
