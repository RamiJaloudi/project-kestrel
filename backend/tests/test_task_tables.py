"""Task metadata and reassignment contracts exercised through authenticated routes."""
import csv
import io
import uuid

from sqlalchemy import func,select
from test_auth_policy import env,login
from test_document_workflow import upload,BASE
from test_observability_governance import post
from kestrel import models as m

T='/api/v1/tables/tasks'
W='/api/v1/review-work'


def setup_tasks(env,stages=('review','qc')):
    h,_,ids,_=env;c=login(h).json()['csrf_token']
    src=upload(h,c,ids['matter'],file_name='=synthetic-review.txt').json()
    response=post(h,BASE+'/documents/'+src['id']+'/confirm',c,{'snapshot_hash':src['snapshot_hash'],'rationale':'Confirm synthetic source for task metadata export'})
    assert response.status_code==200,response.text
    tasks=[]
    for i,stage in enumerate(stages):
        r=post(h,W+'/sources/'+src['id']+'/tasks',c,{'stage':stage,'assignee_id':ids['lawyer'],'request_key':'table-task-'+str(i),'rationale':'Assign synthetic source work independently of legal approval'})
        assert r.status_code==201,r.text;tasks.append(r.json())
    return src,tasks,c


def bulk(ids,tasks,**kw):
    return {'matter_id':ids['matter'],'items':[{'id':t['id'],'expected_revision':t['revision']} for t in tasks],
        'assignee_id':ids['sme'],'rationale':'Reassign synthetic parallel source work','request_key':str(uuid.uuid4()),**kw}


def test_task_pages_counts_filters_and_strict_contract(env):
    h,_,ids,_=env;src,tasks,c=setup_tasks(env)
    p={'matter_id':ids['matter'],'draw':9,'length':1,'sort':'stage','direction':'desc'}
    r=post(h,T+'/query',c,p);assert r.status_code==200,r.text;v=r.json()
    assert v['draw']==9 and v['recordsTotal']==2 and v['recordsFiltered']==2 and len(v['data'])==1
    row=v['data'][0];assert row['source_id']==src['id'] and row['status']=='assigned' and row['revision']==1 and row['can_reassign']
    assert row['assignee_id']==ids['lawyer'] and row['assignee_name']=='Lawyer'
    assert 'events' not in row and 'rationale' not in row and 'timing' not in row
    assert post(h,T+'/query',c,{**p,'start':1}).json()['data'][0]['id']!=row['id']
    filtered=post(h,T+'/query',c,{**p,'task_filters':{'stage':'qc','mine':True,'status':'assigned'}}).json()
    assert filtered['recordsTotal']==1 and filtered['recordsFiltered']==1
    searched=post(h,T+'/query',c,{**p,'column_filters':{'stage':'qc'}}).json()
    assert searched['recordsTotal']==2 and searched['recordsFiltered']==1
    for extra in [{'sort':'rationale'},{'column_filters':{'password_hash':'x'}},{'task_filters':{'priority':'high'}},{'task_filters':{'status':'approved'}},{'source_filters':{}},{'financial_filters':{}},{'saved_view_id':str(uuid.uuid4())}]:
        denied=post(h,T+'/query',c,{**p,**extra});assert denied.status_code==422,denied.text
    assert post(h,'/api/v1/tables/inventory/query',c,{'matter_id':ids['matter'],'task_filters':{}}).status_code==422


def test_task_selected_exports_are_metadata_text_and_safe_partial_counts(env):
    h,_,ids,_=env;src,tasks,c=setup_tasks(env)
    p={'matter_id':ids['matter'],'ids':[tasks[0]['id'],str(uuid.uuid4())],'format':'csv'}
    r=post(h,T+'/export',c,p);assert r.status_code==200,r.text
    values=list(csv.DictReader(io.StringIO(r.text)))
    assert len(values)==1 and values[0]['id']==tasks[0]['id'] and values[0]['file_name'].startswith("'=")
    assert 'rationale' not in r.text and p['ids'][1] not in r.text and r.headers['x-export-unavailable-count']=='1'
    r=post(h,T+'/export',c,{**p,'format':'xlsx'});assert r.status_code==200,r.text
    from openpyxl import load_workbook
    book=load_workbook(io.BytesIO(r.content),data_only=False)
    assert book.active.max_row==2 and all(cell.data_type!='f' for row in book.active for cell in row)
    book.close()


def test_bulk_reassignment_uses_revision_notifications_and_persisted_replay(env):
    h,sessions,ids,_=env;_,tasks,c=setup_tasks(env)
    p=bulk(ids,tasks)
    people=post(h,T+'/eligible-people',c,{'matter_id':ids['matter'],'items':p['items']})
    assert people.status_code==200,people.text
    assert ids['sme'] in {a['id'] for a in people.json()} and ids['lawyer'] not in {a['id'] for a in people.json()}
    r=post(h,T+'/bulk-reassign',c,p);assert r.status_code==200,r.text;v=r.json()
    assert (v['requested'],v['succeeded'],v['unavailable'])==(2,2,0)
    assert {a['status'] for a in v['results']}=={'reassigned'} and all(a['revision']==2 for a in v['results'])
    with sessions() as db:
        event_count=db.scalar(select(func.count()).select_from(m.ReviewTaskEvent))
        notification_count=db.scalar(select(func.count()).select_from(m.ReviewTaskNotification))
    r=post(h,T+'/bulk-reassign',c,p);assert r.status_code==200,r.text
    assert {a['status'] for a in r.json()['results']}=={'replayed'}
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.ReviewTaskEvent))==event_count
        assert db.scalar(select(func.count()).select_from(m.ReviewTaskNotification))==notification_count
    assert post(h,T+'/bulk-reassign',c,{**p,'rationale':'Changed content must not reuse a successful batch identity'}).status_code==409
    for t in tasks:
        current=h.get(W+'/tasks/'+t['id']).json()
        assert current['revision']==2 and current['state']=='assigned' and current['assignee']['id']==ids['sme']
        assert current['events'][-1]['operation']=='reassign'


def test_bulk_partial_stale_rows_are_not_echoed_and_all_failed_key_is_not_consumed(env):
    h,sessions,ids,_=env;_,tasks,c=setup_tasks(env)
    p=bulk(ids,tasks);p['items'][1]['expected_revision']=99
    r=post(h,T+'/bulk-reassign',c,p);assert r.status_code==200,r.text
    assert r.json()['succeeded']==1 and r.json()['unavailable']==1 and tasks[1]['id'] not in r.text
    # There is deliberately no batch ledger: an entirely failed attempt consumes no key.
    failed=bulk(ids,[tasks[1]]);failed['items'][0]['expected_revision']=99
    r=post(h,T+'/bulk-reassign',c,failed);assert r.status_code==200 and r.json()['succeeded']==0
    repaired={**failed,'items':[{'id':tasks[1]['id'],'expected_revision':1}]}
    r=post(h,T+'/bulk-reassign',c,repaired);assert r.status_code==200 and r.json()['succeeded']==1,r.text
    with sessions() as db:assert db.scalar(select(func.count()).select_from(m.ReviewTaskEvent))==4


def test_bulk_changed_disjoint_selection_conflicts_after_success_and_input_is_bounded(env):
    h,_,ids,_=env;_,tasks,c=setup_tasks(env)
    p=bulk(ids,[tasks[0]])
    assert post(h,T+'/bulk-reassign',c,p).json()['succeeded']==1
    changed={**p,'items':[{'id':tasks[1]['id'],'expected_revision':1}]}
    assert post(h,T+'/bulk-reassign',c,changed).status_code==409
    for extra in [{'items':[]},{'items':[p['items'][0],p['items'][0]]},{'items':[{'id':str(uuid.uuid4()),'expected_revision':1} for _ in range(26)]},{'request_key':'not-a-uuid'},{'operation':'complete'}]:
        assert post(h,T+'/bulk-reassign',c,{**p,**extra}).status_code==422


def test_bulk_final_authorization_refusal_rolls_back_events_and_notifications(env,monkeypatch):
    from fastapi import HTTPException
    from kestrel.services import data_tables
    h,sessions,ids,_=env;_,tasks,c=setup_tasks(env)
    with sessions() as db:
        before_events=db.scalar(select(func.count()).select_from(m.ReviewTaskEvent))
        before_notifications=db.scalar(select(func.count()).select_from(m.ReviewTaskNotification))
    def deny(*args,**kwargs):raise HTTPException(409,'Authorization changed before command commit')
    monkeypatch.setattr(data_tables,'finish',deny)
    r=post(h,T+'/bulk-reassign',c,bulk(ids,tasks));assert r.status_code==409,r.text
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.ReviewTaskEvent))==before_events
        assert db.scalar(select(func.count()).select_from(m.ReviewTaskNotification))==before_notifications


def test_successful_bulk_uuid_cannot_be_reused_for_a_different_authorized_matter(env):
    from kestrel.services.auth import clock
    h,sessions,ids,_=env;_,tasks,c=setup_tasks(env,stages=('review',))
    with sessions() as db:
        for uid in [ids['lawyer'],ids['sme']]:db.add(m.MatterAssignment(account_id=uid,matter_id=ids['other'],expires_at=clock()+3600))
        db.commit()
    other=upload(h,c,ids['other'],logical_key='OTHER-TASK',file_name='other-synthetic.txt').json()
    created=post(h,W+'/sources/'+other['id']+'/tasks',c,{'stage':'review','assignee_id':ids['lawyer'],'request_key':'other-task-uuid-test','rationale':'Separate authorized matter source work'})
    assert created.status_code==201,created.text
    p=bulk(ids,tasks);assert post(h,T+'/bulk-reassign',c,p).json()['succeeded']==1
    changed={**p,'matter_id':ids['other'],'items':[{'id':created.json()['id'],'expected_revision':1}]}
    r=post(h,T+'/bulk-reassign',c,changed);assert r.status_code==409,r.text
    assert h.get(W+'/tasks/'+created.json()['id']).json()['revision']==1


def test_bulk_reassignment_stops_existing_reader_lease_without_fabricating_activity(env):
    h,sessions,ids,_=env;_,tasks,c=setup_tasks(env,stages=('review',));task=tasks[0]
    for operation in ['accept','start']:
        r=post(h,W+'/tasks/'+task['id']+'/events',c,{'operation':operation,'expected_revision':task['revision'],'request_key':'before-bulk-'+operation,'rationale':'Assignee records their own actual review activity'})
        assert r.status_code==201,r.text;task=r.json()
    r=post(h,'/api/v1/review-clocks/tasks/'+task['id']+'/sessions',c,{'expected_revision':task['revision'],'request_key':'before-bulk-reader-session'})
    assert r.status_code==201 and r.json()['active'],r.text;session=r.json()
    r=post(h,T+'/bulk-reassign',c,bulk(ids,[task]));assert r.status_code==200 and r.json()['succeeded']==1,r.text
    with sessions() as db:
        receipts=list(db.scalars(select(m.ReviewSessionReceipt).where(m.ReviewSessionReceipt.session_id==session['id'])))
        assert len(receipts)==1 and receipts[0].operation=='task_stop' and receipts[0].mode=='unobserved'
        assert receipts[0].interaction is False
    current=h.get('/api/v1/review-clocks/sessions/'+session['id']).json()
    assert current['active'] is False and current['active_seconds']==0
