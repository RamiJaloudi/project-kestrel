import json
import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy import select,func,text
from test_auth_policy import env,login
from test_ddr_checklists import publish,change,ITEM
from test_document_workflow import upload
from test_observability_governance import post

B='/api/v1/checklist-records'

def test_normalized_items_links_and_history_are_lossless(env):
    from kestrel.models import ChecklistItemRecord,DocumentChecklistLink,ChecklistCoverageProjection
    http,sessions,ids,_=env;v=publish(env);csrf=login(http).json()['csrf_token'];s=upload(http,csrf,ids['matter']).json()
    assert change(http,v,csrf,'PARTIAL',source_ids=[s['id']],missing_information='Awaiting amendments').status_code==201
    c=http.get('/api/v1/checklists/'+v['id']+'/coverage').json()['items'][0]
    assert c['status']=='PARTIAL'
    assert post(http,'/api/v1/checklists/'+v['id']+'/coverage/'+ITEM,csrf,{'expected_revision':1,'status':'UNDER_REVIEW','source_ids':[s['id']],'rationale':'Evidence now being reviewed'}).status_code==201
    history=http.get(B+'/'+v['id']+'/items/'+ITEM+'/history');assert history.status_code==200,history.text
    assert [r['recorded_status'] for r in history.json()['coverage']]==['PARTIAL','UNDER_REVIEW']
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(ChecklistItemRecord))==1
        assert db.scalar(select(func.count()).select_from(DocumentChecklistLink))==2
        assert db.scalar(select(func.count()).select_from(ChecklistCoverageProjection))==2
        for table in ['checklist_coverage_versions','document_checklist_links','checklist_items']:
            with pytest.raises(DBAPIError):db.execute(text('DELETE FROM '+table));db.commit()
            db.rollback()

def test_request_log_private_notes_and_source_bound_sharing(env):
    http,_,ids,_=env;v=publish(env);csrf=login(http).json()['csrf_token']
    p={'operation':'request','expected_revision':0,'request_key':'request-log-001','notes':'Synthetic seller request only','due_date':'2027-01-15','wave':'wave2','workstream':'Commercial','jurisdiction':'Applicability unconfirmed','source_ids':[]}
    r=post(http,B+'/'+v['id']+'/items/'+ITEM+'/requests',csrf,p);assert r.status_code==201,r.text
    assert post(http,B+'/'+v['id']+'/items/'+ITEM+'/requests',csrf,p).json()['id']==r.json()['id']
    login(http,'sme');h=http.get(B+'/'+v['id']+'/items/'+ITEM+'/history').json();assert h['requests']==[]
    csrf=login(http).json()['csrf_token'];s=upload(http,csrf,ids['matter']).json()
    r=post(http,B+'/'+v['id']+'/items/'+ITEM+'/requests',csrf,{**p,'operation':'follow_up','expected_revision':1,'request_key':'request-log-002','source_ids':[s['id']]});assert r.status_code==201
    login(http,'sme');assert len(http.get(B+'/'+v['id']+'/items/'+ITEM+'/history').json()['requests'])==1
    login(http,'root');assert http.get(B+'/'+v['id']+'/items/'+ITEM+'/history').status_code==403

def test_waiver_needs_independent_sme_and_keeps_raw_coverage(env):
    http,_,ids,_=env;v=publish(env);csrf=login(http).json()['csrf_token'];base='/api/v1/checklists/'+v['id']
    r=post(http,base+'/coverage/'+ITEM+'/waiver-requests',csrf,{'expected_revision':0,'rationale':'Request-specific waiver for synthetic missing material'});assert r.status_code==201,r.text
    key=r.json()['id']
    assert post(http,base+'/waiver-requests/'+key+'/approve',csrf,{'expected_revision':1,'rationale':'Cannot approve my own waiver proposal'}).status_code==403
    csrf=login(http,'sme').json()['csrf_token']
    approved=post(http,base+'/waiver-requests/'+key+'/approve',csrf,{'expected_revision':1,'rationale':'Independent SME accepts this specific request waiver'});assert approved.status_code==200,approved.text
    assert approved.json()['status']=='WAIVED_BY_HUMAN'
    history=http.get(B+'/'+v['id']+'/items/'+ITEM+'/history').json()['coverage'];assert len(history)==2 and history[0]['recorded_status']=='GAP'

def test_new_report_captures_exact_coverage_and_revision_keeps_it(env):
    from test_document_workflow import candidate
    from test_diligence import assessment
    from kestrel.models import ReportChecklistSnapshot
    http,sessions,ids,_=env;s,f,csrf=candidate(env);v=publish(env);csrf=login(http).json()['csrf_token']
    assert change(http,v,csrf,'RECEIVED',source_ids=[s['id']]).status_code==201
    report=post(http,'/api/v1/reports/generate',csrf,{'matter_id':ids['matter'],'audience':'halden','kind':'due_diligence','title':'Synthetic coverage provenance report','finding_ids':[f['id']]}).json()
    r=http.get(B+'/reports/'+report['id']+'/coverage');assert r.status_code==200,r.text
    assert r.json()['snapshots'][0]['recorded_status']=='RECEIVED'
    assert post(http,'/api/v1/checklists/'+v['id']+'/coverage/'+ITEM,csrf,{'expected_revision':1,'status':'UNDER_REVIEW','source_ids':[s['id']],'rationale':'Later document review status'}).status_code==201
    assert http.get(B+'/reports/'+report['id']+'/coverage').json()['snapshots'][0]['recorded_status']=='RECEIVED'
    body=report['body'];edit={k:body[k] for k in ['title','overview','coverage']};edit['sections']=[{k:section[k] for k in ['heading','text']} for section in body['sections']]
    newer=post(http,'/api/v1/reports/'+report['id']+'/versions',csrf,edit);assert newer.status_code==201,newer.text
    assert http.get(B+'/reports/'+newer.json()['id']+'/coverage').json()['snapshots'][0]['recorded_status']=='RECEIVED'


def test_partial_needs_evidence_and_missing_info_and_history_obeys_walls(env):
    from kestrel.models import EthicalWall
    http,sessions,ids,_=env;v=publish(env);csrf=login(http).json()['csrf_token']
    assert change(http,v,csrf,'PARTIAL',missing_information='Awaiting documents').status_code==422
    src=upload(http,csrf,ids['matter']).json()
    assert change(http,v,csrf,'PARTIAL',source_ids=[src['id']]).status_code==422
    assert change(http,v,csrf,'PARTIAL',source_ids=[src['id']],missing_information='Awaiting amendments').status_code==201
    with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    assert http.get(B+'/'+v['id']+'/items/'+ITEM+'/history').status_code==403
