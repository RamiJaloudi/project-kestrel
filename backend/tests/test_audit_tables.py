"""Permitted audit windows, shared query/export selection and fresh authority."""
import csv
import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete,func,select
from test_auth_policy import env,login
from test_observability_governance import post
from kestrel import models as m
from kestrel.services.auth import clock

A='/api/v1/audit'
FIELDS={'id','occurred_at','actor_id','category','matter_id','object_id','clean_team_scope','action','outcome','correlation_id'}


def seed(sessions,ids,**changes):
    with sessions() as db:
        row=m.AuditEvent(**{'occurred_at':20,'actor_id':ids['lawyer'],'category':'legal_sme','matter_id':ids['matter'],'action':'synthetic.audit','outcome':'allowed',**changes})
        db.add(row);db.flush();key=row.id;db.commit();return key


def grant(sessions,ids,role='matter_auditor',account='lawyer'):
    with sessions() as db:
        value=db.scalar(select(m.Role).where(m.Role.name==role))
        if value is None:value=m.Role(name=role);db.add(value);db.flush()
        db.add(m.RoleGrant(account_id=ids[account],role_id=value.id));db.commit()


def scopes(sessions,ids,account='lawyer',scope='pricing',expires=None):
    with sessions() as db:
        db.add(m.CleanTeamMembership(account_id=ids[account],matter_id=ids['matter'],scope=scope,approved_by=ids['sme'],expires_at=expires or clock()+600));db.commit()


def query(http,csrf,category='legal_sme',**changes):
    return post(http,A+'/query',csrf,{'audit_filters':{'category':category},**changes})


def withheld(response,*canaries):
    assert response.status_code in {401,403,409},response.text
    assert 'recordsTotal' not in response.text and 'content-disposition' not in response.headers
    assert all(value not in response.text for value in canaries)


def revoke(sessions,ids,kind):
    with sessions() as db:
        if kind=='session':
            for row in db.scalars(select(m.ServerSession).where(m.ServerSession.account_id==ids['lawyer'])):row.revoked=True
        elif kind=='wall':db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True))
        elif kind=='membership':
            for row in db.scalars(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'])):row.expires_at=clock()-1
        elif kind=='grant':
            role=db.scalar(select(m.Role.id).where(m.Role.name=='matter_auditor'))
            db.execute(delete(m.RoleGrant).where(m.RoleGrant.account_id==ids['lawyer'],m.RoleGrant.role_id==role))
        db.commit()


def test_query_own_scope_typed_counts_literal_filters_stable_paging_and_no_self_audit(env):
    http,sessions,ids,_=env
    own=[seed(sessions,ids,id='audit-'+str(n),action='same action',occurred_at=10+n,outcome='allowed' if n<2 else 'denied') for n in range(3)]
    seed(sessions,ids,actor_id=ids['sme'],action='OTHER_ACTOR_PRIVATE')
    seed(sessions,ids,matter_id=ids['other'],action='OTHER_MATTER_PRIVATE')
    csrf=login(http).json()['csrf_token']
    with sessions() as db:before=db.scalar(select(func.count()).select_from(m.AuditEvent))
    payload={'draw':7,'length':1,'sort':'action','column_filters':{'outcome':'allowed'}}
    r=query(http,csrf,**payload);assert r.status_code==200,r.text
    first=r.json();assert (first['draw'],first['recordsTotal'],first['recordsFiltered'])==(7,3,2)
    assert set(first['data'][0])==FIELDS and first['data'][0]['id']==own[0]
    assert query(http,csrf,**{**payload,'start':1}).json()['data'][0]['id']==own[1]
    assert query(http,csrf,search='.*').json()['recordsFiltered']==0
    assert 'PRIVATE' not in r.text and 'details' not in r.text
    with sessions() as db:assert db.scalar(select(func.count()).select_from(m.AuditEvent))==before


def test_explicit_auditor_grant_and_time_scope_precede_counts(env):
    http,sessions,ids,_=env
    seed(sessions,ids,occurred_at=10);selected=seed(sessions,ids,occurred_at=20,actor_id=ids['sme'])
    seed(sessions,ids,occurred_at=20,matter_id=ids['other'],actor_id=ids['sme'],action='FOREIGN_PRIVATE')
    csrf=login(http).json()['csrf_token'];assert query(http,csrf).json()['recordsTotal']==1
    grant(sessions,ids)
    r=query(http,csrf,audit_filters={'category':'legal_sme','matter_id':ids['matter'],'from_time':15,'to_time':25})
    assert r.status_code==200 and r.json()['recordsTotal']==1 and r.json()['data'][0]['id']==selected,r.text
    with sessions() as db:db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    withheld(query(http,csrf,audit_filters={'category':'legal_sme','matter_id':ids['matter']}),'FOREIGN_PRIVATE')


def test_root_administrative_audit_does_not_grant_clean_team_or_legal_override(env):
    http,sessions,ids,_=env
    seed(sessions,ids,category='administrative',matter_id=None,actor_id=ids['sme'])
    seed(sessions,ids,category='legal_sme',actor_id=ids['sme'])
    seed(sessions,ids,category='clean_team',clean_team_scope='pricing',actor_id=ids['sme'])
    csrf=login(http,'root').json()['csrf_token']
    assert query(http,csrf,'administrative').json()['recordsTotal']>=1
    assert query(http,csrf).json()['recordsTotal']==0
    withheld(query(http,csrf,'clean_team'))


@pytest.mark.parametrize('name,host',[('client','client'),('bank','bank')])
def test_external_audit_is_own_metadata_not_firm_or_other_external_events(env,name,host):
    _,sessions,ids,app=env
    own=seed(sessions,ids,actor_id=ids[name]);seed(sessions,ids,action='PRIVATE_FIRM_EVENT')
    with TestClient(app,base_url='https://'+host+'.localhost') as http:
        origin='https://'+host+'.localhost';csrf=login(http,name,origin).json()['csrf_token']
        r=http.post(A+'/query',json={'audit_filters':{'category':'legal_sme'}},headers={'origin':origin,'x-csrf-token':csrf})
        assert r.status_code==200 and [row['id'] for row in r.json()['data']]==[own] and 'PRIVATE' not in r.text,r.text


def test_named_clean_team_scopes_and_retained_work_union_filter_before_counts(env):
    from test_task_data_tables import scopes as task_scopes,two_scope_history
    http,sessions,ids,_=env
    task_scopes(sessions,ids,[ids['lawyer']], 'pricing','strategy')
    csrf=login(http).json()['csrf_token'];_,task=two_scope_history(http,csrf,sessions,ids,'audit-retained')
    private=seed(sessions,ids,category='clean_team',clean_team_scope='pricing',object_id=task['id'],action='RETAINED_PRIVATE_TASK')
    visible=seed(sessions,ids,category='clean_team',clean_team_scope='pricing',action='visible.audit')
    with sessions() as db:
        for row in db.scalars(select(m.CleanTeamMembership).where(m.CleanTeamMembership.scope=='strategy')):row.revoked=True
        db.commit()
    r=query(http,csrf,'clean_team',column_filters={'action':'RETAINED_PRIVATE_TASK'})
    assert r.status_code==200 and r.json()['recordsFiltered']==0,r.text
    assert private not in json.dumps(r.json())
    assert visible in [row['id'] for row in query(http,csrf,'clean_team',length=50).json()['data']]
    with sessions() as db:
        for row in db.scalars(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'])):row.expires_at=clock()-1
        db.commit()
    withheld(query(http,csrf,'clean_team'))


@pytest.mark.parametrize('extra',[{}, {'draw':True},{'start':-1},{'length':51},{'sort':'details'},{'direction':'sideways'},
    {'search':{'regex':True}},{'column_filters':{'password':'x'}},{'column_filters':{'id':False}},
    {'audit_filters':{'category':'everything'}},{'audit_filters':{'category':'access','from_time':True}},
    {'audit_filters':{'category':'access','from_time':'20'}},{'audit_filters':{'category':'access','to_time':-1}},
    {'audit_filters':{'category':'access','from_time':30,'to_time':20}},
    {'audit_filters':{'category':'access','scope':'pricing'}},{'matter_id':'wrong-place'},{'saved_view_id':'unsupported'},
    {'account_filters':{}},{'source_filters':{}},{'format':'csv'}])
def test_strict_audit_query_rejects_wrong_or_untyped_fields(env,extra):
    http,_,_,_=env;csrf=login(http).json()['csrf_token']
    body={'audit_filters':{'category':'access'},**extra} if extra else {}
    assert post(http,A+'/query',csrf,body).status_code==422


def test_permitted_baseline_1001_is_rejected_before_search_or_export(env):
    http,sessions,ids,_=env
    with sessions() as db:
        db.add_all([m.AuditEvent(occurred_at=20,actor_id=ids['lawyer'],category='legal_sme',matter_id=ids['matter'],action='synthetic.volume',outcome='allowed') for _ in range(1001)]);db.commit()
    csrf=login(http).json()['csrf_token'];payload={'audit_filters':{'category':'legal_sme'},'search':'NO_MATCH'}
    assert post(http,A+'/query',csrf,payload).status_code==413
    assert post(http,A+'/export-query',csrf,{**payload,'format':'csv'}).status_code==413


def test_nonpermitted_events_do_not_consume_baseline_ceiling(env):
    http,sessions,ids,_=env
    with sessions() as db:
        db.add_all([m.AuditEvent(occurred_at=20,actor_id=ids['sme'],category='legal_sme',matter_id=ids['matter'],action='HIDDEN_VOLUME',outcome='allowed') for _ in range(1001)]);db.commit()
    own=seed(sessions,ids);csrf=login(http).json()['csrf_token']
    r=query(http,csrf);assert r.status_code==200 and r.json()['recordsTotal']==1 and r.json()['data'][0]['id']==own,r.text
    assert 'HIDDEN_VOLUME' not in r.text


def test_offpage_nonmatching_event_grant_loss_still_withholds_page(env,monkeypatch):
    from kestrel.services import audit_tables
    http,sessions,ids,_=env;grant(sessions,ids)
    seed(sessions,ids,action='PUBLIC_MATCH');private=seed(sessions,ids,actor_id=ids['sme'],action='HIDDEN_NONMATCH')
    csrf=login(http).json()['csrf_token'];original=audit_tables.filtered;fired=False
    def prepare_then_revoke(*args,**kwargs):
        nonlocal fired
        result=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,'grant')
        return result
    monkeypatch.setattr(audit_tables,'filtered',prepare_then_revoke)
    r=query(http,csrf,search='PUBLIC_MATCH',length=1)
    assert fired;withheld(r,private,'HIDDEN_NONMATCH')


def test_html_export_escapes_metadata_and_unknown_formats_fail_closed(env):
    http,sessions,ids,_=env;seed(sessions,ids,action='<script>PRIVATE_MARKUP</script>')
    csrf=login(http).json()['csrf_token'];payload={'audit_filters':{'category':'legal_sme'},'format':'html'}
    r=post(http,A+'/export-query',csrf,payload);assert r.status_code==200,r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:data=archive.read('events.html').decode()
    assert '<script>' not in data and '&lt;script&gt;PRIVATE_MARKUP&lt;/script&gt;' in data
    assert post(http,A+'/export-query',csrf,{**payload,'format':'xlsx'}).status_code==422
    assert post(http,A+'/export-query',csrf,{**payload,'selected_ids':['arbitrary']}).status_code==422


def test_export_rechecks_retained_work_union_when_current_source_and_named_scope_stay_unchanged(env,monkeypatch):
    from test_task_data_tables import scopes as task_scopes,two_scope_history
    from kestrel.services import auditing
    http,sessions,ids,_=env;task_scopes(sessions,ids,[ids['lawyer']],'pricing','strategy')
    csrf=login(http).json()['csrf_token'];_,task=two_scope_history(http,csrf,sessions,ids,'audit-render-retained')
    private=seed(sessions,ids,category='clean_team',clean_team_scope='pricing',object_id=task['id'],action='RETAINED_RENDER_PRIVATE')
    original=auditing.render;fired=False
    def render_then_lose_retained_scope(*args,**kwargs):
        nonlocal fired
        result=original(*args,**kwargs)
        if not fired:
            fired=True
            with sessions() as db:
                for row in db.scalars(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'],m.CleanTeamMembership.scope=='strategy')):row.revoked=True
                db.commit()
        return result
    monkeypatch.setattr(auditing,'render',render_then_lose_retained_scope)
    r=post(http,A+'/export-query',csrf,{'audit_filters':{'category':'clean_team'},'search':'RETAINED_RENDER_PRIVATE','format':'csv'})
    assert fired;withheld(r,private,'RETAINED_RENDER_PRIVATE')


@pytest.mark.parametrize('format',['jsonl','csv','html','pdf'])
def test_export_query_is_all_filtered_not_page_and_manifest_binds_exact_applied_descriptor(env,monkeypatch,format):
    from kestrel.adapters import audit_pdf
    http,sessions,ids,_=env
    expected=[seed(sessions,ids,id='export-'+str(n),action='=UNTRUSTED_'+str(n),occurred_at=20+n) for n in range(3)]
    seed(sessions,ids,action='not matched');seed(sessions,ids,actor_id=ids['sme'],action='=PRIVATE')
    monkeypatch.setattr(audit_pdf,'render',lambda rows,actor,filters:b'%PDF synthetic scoped audit')
    csrf=login(http).json()['csrf_token']
    payload={'draw':4,'start':1,'length':1,'sort':'occurred_at','direction':'desc','search':'=UNTRUSTED','column_filters':{'outcome':'allow'},
             'audit_filters':{'category':'legal_sme','matter_id':ids['matter'],'from_time':10,'to_time':30}}
    page=post(http,A+'/query',csrf,payload).json();assert page['recordsTotal']==4 and page['recordsFiltered']==3 and len(page['data'])==1
    r=post(http,A+'/export-query',csrf,{**payload,'format':format});assert r.status_code==200,r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        data=archive.read('events.'+format);manifest=json.loads(archive.read('manifest.json'))
    assert manifest['event_ids']==list(reversed(expected)) and manifest['count']==3
    assert manifest['sha256']==hashlib.sha256(data).hexdigest() and not manifest['immutable_storage']
    applied=manifest['filters'];assert applied['audit_filters']==payload['audit_filters'] and applied['search']==payload['search']
    assert applied['column_filters']==payload['column_filters'] and applied['sort']=='occurred_at' and applied['direction']=='desc'
    assert applied['selection']=='all_filtered' and manifest['exported_by']==ids['lawyer']
    if format=='csv':
        rows=list(csv.DictReader(io.StringIO(data.decode())));assert len(rows)==3 and rows[0]['action'].startswith("'=")
    if format=='jsonl':assert [json.loads(line)['id'] for line in data.decode().splitlines()]==list(reversed(expected))
    assert r.headers['cache-control']=='no-store'


@pytest.mark.parametrize('operation',['query','events','export','export-query'])
@pytest.mark.parametrize('kind',['session','wall','grant','membership'])
def test_read_and_render_withhold_after_cookie_wall_or_grant_changes(env,monkeypatch,operation,kind):
    from kestrel.services import auditing
    from kestrel.api import auditing as routes
    http,sessions,ids,_=env
    category='clean_team' if kind=='membership' else 'legal_sme'
    if kind=='membership':scopes(sessions,ids)
    if kind=='grant':grant(sessions,ids)
    private=seed(sessions,ids,actor_id=ids['sme'] if kind=='grant' else ids['lawyer'],category=category,clean_team_scope='pricing' if kind=='membership' else None,action='RACE_PRIVATE')
    csrf=login(http).json()['csrf_token'];fired=False
    hook='render' if 'export' in operation else 'selected';original=getattr(auditing,hook)
    def prepared_then_revoke(*args,**kwargs):
        nonlocal fired
        value=original(*args,**kwargs)
        if not fired:fired=True;revoke(sessions,ids,kind)
        return value
    monkeypatch.setattr(auditing,hook,prepared_then_revoke)
    # Old API imported these helpers directly before the new shared service.
    if hasattr(routes,hook):monkeypatch.setattr(routes,hook,prepared_then_revoke)
    if operation in {'events','export'}:r=http.get(A+'/'+operation,params={'category':category,**({'format':'csv'} if operation=='export' else {})})
    else:r=post(http,A+'/'+operation,csrf,{'audit_filters':{'category':category},**({'format':'csv'} if operation=='export-query' else {})})
    assert fired;withheld(r,private,'RACE_PRIVATE')
    if 'export' in operation:
        with sessions() as db:assert db.scalar(select(func.count()).select_from(m.AuditEvent).where(m.AuditEvent.action=='audit.export',m.AuditEvent.outcome=='allowed'))==0


def test_audit_response_model_documents_exact_metadata_not_untyped_objects(env):
    _,_,_,app=env;schema=app.openapi();route=schema['paths'][A+'/query']['post']
    ref=route['responses']['200']['content']['application/json']['schema']['$ref'].split('/')[-1]
    page=schema['components']['schemas'][ref];assert set(page['properties'])=={'draw','recordsTotal','recordsFiltered','data','count_basis'}
    row=page['properties']['data']['items']['$ref'].split('/')[-1]
    assert set(schema['components']['schemas'][row]['properties'])==FIELDS


@pytest.mark.parametrize('operation',['query','events','export','export-query'])
@pytest.mark.parametrize('kind',['grant','membership','source','retained_event'])
def test_final_selector_pass_cannot_emit_after_authority_input_changes(env,monkeypatch,operation,kind):
    """Revocation AFTER the final selection must invalidate its prepared result."""
    from kestrel.services import auditing
    from test_table_security_review import confirmed
    from test_task_data_tables import create_task
    http,sessions,ids,_=env;category='legal_sme' if kind=='grant' else 'clean_team'
    csrf=login(http).json()['csrf_token'];source=None;task=None
    if kind=='grant':grant(sessions,ids)
    else:scopes(sessions,ids)
    if kind=='source':source=confirmed(http,csrf,ids['matter'],logical_key='AUDIT-FINAL-SOURCE',file_name='final-source.txt')
    if kind=='retained_event':source,task=create_task(http,csrf,ids['matter'],ids['lawyer'],'audit-final-retained')
    private=seed(sessions,ids,actor_id=ids['sme'] if kind=='grant' else ids['lawyer'],category=category,
        clean_team_scope='pricing' if category=='clean_team' else None,
        object_id=task['id'] if task else source['id'] if source else None,action='FINAL_SELECTOR_PRIVATE')
    original=auditing.selected;calls=0;final_call=3 if 'export' in operation else 2
    def select_then_change_final_authority(*args,**kwargs):
        nonlocal calls
        result=original(*args,**kwargs);calls+=1
        if calls==final_call:
            if kind in {'grant','membership'}:revoke(sessions,ids,kind)
            else:
                with sessions() as db:
                    if kind=='source':
                        policy=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,source['id']).policy_id)
                        policy.classification='clean_team';policy.clean_team_scope='strategy'
                    else:
                        previous=db.scalar(select(m.ReviewTaskEvent).where(m.ReviewTaskEvent.task_id==task['id']).order_by(m.ReviewTaskEvent.revision.desc()))
                        values={column.name:getattr(previous,column.name) for column in m.ReviewTaskEvent.__table__.columns if column.name!='id'}
                        values.update(revision=previous.revision+1,request_key='final-retained-event',input_hash='0'*64,
                            retained_classification='clean_team',retained_scope='strategy')
                        db.add(m.ReviewTaskEvent(**values))
                    db.commit()
        return result
    monkeypatch.setattr(auditing,'selected',select_then_change_final_authority)
    if operation in {'events','export'}:r=http.get(A+'/'+operation,params={'category':category,**({'format':'csv'} if operation=='export' else {})})
    else:r=post(http,A+'/'+operation,csrf,{'audit_filters':{'category':category},**({'format':'csv'} if operation=='export-query' else {})})
    assert calls==final_call;withheld(r,private,'FINAL_SELECTOR_PRIVATE')
    if 'export' in operation:
        with sessions() as db:assert db.scalar(select(func.count()).select_from(m.AuditEvent).where(m.AuditEvent.action=='audit.export',m.AuditEvent.outcome=='allowed'))==0


@pytest.mark.parametrize('kind',['label_json','label_hash','checklist_json','unknown_classification','missing_clean_scope'])
def test_malformed_security_receipts_fail_closed_without_driver_or_rationale_disclosure(env,kind):
    from test_table_security_review import confirmed
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    source=confirmed(http,csrf,ids['matter'],logical_key='AUDIT-MALFORMED',file_name='malformed-fixture.txt')
    with sessions() as db:
        if kind in {'label_json','label_hash'}:
            db.add(m.ContentLabelAssertion(matter_id=ids['matter'],source_id=source['id'],retained_classification='ordinary',retained_scope=None,
                version_number=1,labels_json='MALFORMED_PRIVATE_DRIVER' if kind=='label_json' else '["legal"]',label_scope=None,unit_number=None,start_offset=None,end_offset=None,
                evidence_hash='0'*64,source_bytes_hash=source['bytes_hash'],source_text_hash=source['text_hash'],provenance_kind='manual',
                classifier_version='synthetic-fixture',confidence=None,rationale='PRIVATE_RETAINED_RATIONALE',created_by=ids['lawyer'],
                request_key='malformed-audit-fixture',input_hash='0'*64,content_hash='0'*64,created_at=clock()))
        else:
            version=m.ChecklistVersion(matter_id=ids['matter'],version_number=1,author_id=ids['lawyer'],definition_json='{}',content_hash='0'*64,
                request_key='malformed-audit-fixture',input_hash='0'*64,created_at=clock());db.add(version);db.flush()
            snapshots=('MALFORMED_PRIVATE_DRIVER' if kind=='checklist_json' else json.dumps({'_restrictions':[
                {'matter_id':ids['matter'],'classification':'MALFORMED_PRIVATE_DRIVER' if kind=='unknown_classification' else 'clean_team','clean_team_scope':None}]}))
            db.add(m.ChecklistCoverageDecision(version_id=version.id,item_id='synthetic-item',revision=1,actor_id=ids['lawyer'],kind='coverage',status='GAP',
                source_ids_json=json.dumps([source['id']]),finding_ids_json='[]',source_snapshots_json=snapshots,missing_information='PRIVATE_RETAINED_RATIONALE',
                rationale='PRIVATE_RETAINED_RATIONALE',created_at=clock()))
        db.commit()
    seed(sessions,ids,action='PRIVATE_PENDING_EVENT')
    r=query(http,csrf);assert r.status_code==409,r.text
    withheld(r,'PRIVATE_PENDING_EVENT','MALFORMED_PRIVATE_DRIVER','PRIVATE_RETAINED_RATIONALE')


def test_valid_retained_attribute_integrity_receipt_does_not_disclose_assertion_body(env):
    from test_table_security_review import confirmed
    from test_content_labels import proposal
    http,_,ids,_=env;csrf=login(http).json()['csrf_token']
    source=confirmed(http,csrf,ids['matter'],logical_key='AUDIT-VALID-LABEL',file_name='valid-label.txt')
    asserted=proposal(http,csrf,source,rationale='PRIVATE_ATTRIBUTE_RATIONALE');assert asserted.status_code==201,asserted.text
    r=query(http,csrf);assert r.status_code==200,r.text
    assert 'PRIVATE_ATTRIBUTE_RATIONALE' not in r.text and 'evidence_hash' not in r.text
    r=post(http,A+'/export-query',csrf,{'audit_filters':{'category':'legal_sme'},'format':'jsonl'});assert r.status_code==200,r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        assert 'PRIVATE_ATTRIBUTE_RATIONALE' not in archive.read('events.jsonl').decode()


@pytest.mark.parametrize('family',['reconciliation','table_view_share'])
@pytest.mark.parametrize('operation',['query','export-query'])
def test_final_resolver_redirect_to_existing_restricted_records_invalidates_output(env,monkeypatch,family,operation):
    """Instrument a corrupted resolver binding; never disable immutable DB guards."""
    from decimal import Decimal
    from test_table_security_review import confirmed
    from kestrel.services import auditing,review_work
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];scopes(sessions,ids)
    source=confirmed(http,csrf,ids['matter'],logical_key='AUDIT-RESOLVER',file_name='resolver-fixture.txt')
    with sessions() as db:
        if family=='reconciliation':
            facts=[]
            for index,classification,scope in [(1,'ordinary',None),(2,'clean_team','strategy')]:
                fact=m.FinancialFact(matter_id=ids['matter'],source_id=source['id'],retained_classification=classification,retained_scope=scope,
                    evidence_key=str(index)*64,reference_kind='source',reference_id=source['id'],reference_snapshot='0'*64,entity='Synthetic fixture',
                    metric='revenue',period_start='2025-01-01',period_end='2025-12-31',currency='USD',scale='1',accounting_basis='UNKNOWN',
                    consolidation_scope='UNKNOWN',amount_text='1',amount=Decimal('1'),evidence_json='[]',content_hash='0'*64,created_by=ids['lawyer'],created_at=clock())
                db.add(fact);db.flush();facts.append(fact)
            containers=[]
            for index,left in enumerate(facts,1):
                case=m.FinancialReconciliation(matter_id=ids['matter'],left_id=left.id,right_id=facts[0].id,content_hash=str(index)*64,
                    calculation_json='{}',created_by=ids['lawyer'],created_at=clock());db.add(case);db.flush();containers.append(case.id)
        else:
            versions=[]
            for index,classification,scope in [(1,'ordinary',None),(2,'clean_team','strategy')]:
                view=m.TableView(matter_id=ids['matter'],dataset='inventory',owner_id=ids['lawyer'],organization='firm',created_at=clock())
                db.add(view);db.flush()
                version=m.TableViewVersion(view_id=view.id,matter_id=ids['matter'],revision=1,name='Synthetic resolver fixture',query_json='{}',handling='source_bound',
                    rationale='PRIVATE_RESOLVER_RATIONALE',content_hash=str(index)*64,created_by=ids['lawyer'],created_at=clock(),request_key='resolver-'+str(index),input_hash='0'*64)
                db.add(version);db.flush();versions.append(version.id)
                db.add(m.TableViewEvidence(version_id=version.id,matter_id=ids['matter'],source_id=source['id'],retained_classification=classification,retained_scope=scope,
                    kind='source',reference_id=source['id'],reference_snapshot='0'*64))
            share=m.TableViewShare(matter_id=ids['matter'],version_id=versions[0],version_hash='1'*64,requested_by=ids['lawyer'],expires_at=clock()+600,
                rationale='PRIVATE_RESOLVER_RATIONALE',content_hash='3'*64,created_at=clock(),request_key='resolver-share',input_hash='0'*64)
            db.add(share);db.flush();containers=[share.id,versions[1]]
        db.commit()
    private=seed(sessions,ids,category='clean_team',clean_team_scope='pricing',object_id=containers[0],action='FINAL_RESOLVER_PRIVATE')
    original_resolver=review_work.audit_records;redirected=False
    def redirected_binding(db,key):
        return original_resolver(db,containers[1] if redirected and key==containers[0] else key)
    monkeypatch.setattr(review_work,'audit_records',redirected_binding)
    original_selected=auditing.selected;calls=0;final_call=3 if operation=='export-query' else 2
    def selected_then_redirect(*args,**kwargs):
        nonlocal calls,redirected
        result=original_selected(*args,**kwargs);calls+=1
        if calls==final_call:redirected=True
        return result
    monkeypatch.setattr(auditing,'selected',selected_then_redirect)
    r=post(http,A+'/'+operation,csrf,{'audit_filters':{'category':'clean_team'},**({'format':'csv'} if operation=='export-query' else {})})
    assert calls==final_call and redirected;withheld(r,private,'FINAL_RESOLVER_PRIVATE','PRIVATE_RESOLVER_RATIONALE')
