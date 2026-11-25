"""Adversarial cross-domain boundaries; fixtures never modify live application data.

Passing this selected matrix does not establish full production readiness or
complete the wider gate's operational, converter and external-release work.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_document_workflow import upload,candidate,BASE
from test_observability_governance import post
from kestrel import models as m


def wall(sessions,uid,matter):
    with sessions() as db:db.add(m.EthicalWall(account_id=uid,matter_id=matter,active=True));db.commit()


def withheld(response,*private):
    assert response.status_code in {401,403,409},response.text
    assert 'content-disposition' not in response.headers
    for value in private:assert value not in response.text
    for key in ['recordsTotal','recordsFiltered','authorized_count','citations','groups','units']:assert '"'+key+'"' not in response.text


@pytest.mark.parametrize('change',['ethical_wall','session_revoked','account_inactive','assignment_revoked'])
def test_reader_rechecks_current_wall_after_presentation_before_emitting_source_text(env,monkeypatch,change):
    from kestrel.adapters import document_reader
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];source=upload(http,csrf,ids['matter'],file_name='cross-domain-private-reader.txt').json()
    original=document_reader.presentation
    def changed(row):
        value=original(row)
        if change=='ethical_wall':wall(sessions,ids['lawyer'],ids['matter'])
        else:
            with sessions() as db:
                if change=='session_revoked':
                    for session in db.scalars(select(m.ServerSession).where(m.ServerSession.account_id==ids['lawyer'])):session.revoked=True
                elif change=='account_inactive':db.get(m.Account,ids['lawyer']).active=False
                else:db.scalar(select(m.MatterAssignment).where(m.MatterAssignment.account_id==ids['lawyer'],m.MatterAssignment.matter_id==ids['matter'])).revoked=True
                db.commit()
        return value
    monkeypatch.setattr(document_reader,'presentation',changed)
    withheld(http.get(BASE+'/documents/'+source['id']+'/reader'),source['file_name'],'prior written consent')


def test_lexical_answer_rechecks_identity_after_authorized_corpus_was_prepared(env,monkeypatch):
    from kestrel.services import questions
    http,sessions,ids,_=env;source,_,csrf=candidate(env);original=questions.corpus
    def changed(db,actor,payload):
        result=original(db,actor,payload);wall(sessions,ids['lawyer'],ids['matter']);return result
    monkeypatch.setattr(questions,'corpus',changed)
    withheld(post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which change of control requires consent?','mode':'lexical'}),source['id'],'prior written consent')


def test_financial_api_rechecks_identity_before_emitting_amounts_and_counts(env,monkeypatch):
    from test_financial_workflow import source,payload,F
    from kestrel.services import financial
    http,sessions,ids,_=env;src,csrf=source(env);fact=post(http,F+'/facts',csrf,payload(src['id'])).json();original=financial.output
    def changed(db,actor,row,**kwargs):
        result=original(db,actor,row,**kwargs);wall(sessions,ids['lawyer'],ids['matter']);return result
    monkeypatch.setattr(financial,'output',changed)
    withheld(post(http,F+'/query',csrf,{'matter_id':ids['matter']}),src['id'],fact['amount_text'])


@pytest.mark.parametrize('account',['lawyer','root'])
def test_scoring_profile_metadata_rechecks_person_scope_before_response(env,monkeypatch,account):
    from kestrel.services import intelligence_governance as governance
    http,sessions,ids,_=env;root=login(http,'root').json()['csrf_token']
    profile=post(http,'/api/v1/intelligence/profiles',root,{'matter_id':ids['matter'],'name':'Protected strategy naming-772','expected_previous_version':0,'recipient_ids':[ids['lawyer']],'assignee_id':ids['lawyer'],'rationale':'Protected operational strategy metadata requires current person clearance','request_key':uuid.uuid4().hex})
    assert profile.status_code==201,profile.text
    login(http,account);before=http.get('/api/v1/intelligence/profiles?matter_id='+ids['matter']);assert before.status_code==200 and profile.json()['id'] in before.text
    original=governance.profiles;prepared=[]
    def changed(db,actor,matter):
        result=original(db,actor,matter);prepared.append(True);wall(sessions,ids[account],ids['matter']);return result
    monkeypatch.setattr(governance,'profiles',changed)
    withheld(http.get('/api/v1/intelligence/profiles?matter_id='+ids['matter']),'Protected strategy naming-772')
    assert prepared


def test_review_task_detail_rechecks_authority_after_retained_task_projection(env,monkeypatch):
    from test_review_work import task
    from kestrel.services import review_work
    http,sessions,ids,_=env;source,work,csrf=task(env);original=review_work.task_output
    def changed(db,actor,row):
        result=original(db,actor,row);wall(sessions,ids['lawyer'],ids['matter']);return result
    monkeypatch.setattr(review_work,'task_output',changed)
    withheld(http.get('/api/v1/review-work/tasks/'+work['id']),source['id'],'Assign synthetic document review')


def test_report_list_rechecks_authority_after_complete_body_was_prepared(env,tmp_path,monkeypatch):
    from kestrel.services import reports
    http,sessions,ids,_=env;source,finding,view,task,answer,run,csrf=stack(env,tmp_path);original=reports.output
    def changed(*args,**kwargs):
        result=original(*args,**kwargs);wall(sessions,ids['lawyer'],ids['matter']);return result
    monkeypatch.setattr(reports,'output',changed)
    withheld(http.get('/api/v1/reports?matter_id='+ids['matter']),run['title'],'prior written consent')


def saved_view(http,csrf,ids,source):
    response=post(http,'/api/v1/table-views',csrf,{'matter_id':ids['matter'],'dataset':'inventory','name':'Cross-domain private filter metadata','query':{'matter_id':ids['matter'],'search':'consent'},'handling':'source_bound','evidence_refs':[{'kind':'source','id':source['id']}],'rationale':'Retained synthetic query remains subject to every current source and matter restriction','request_key':uuid.uuid4().hex})
    assert response.status_code==201,response.text
    return response.json()


def registry_router(app):
    from kestrel.api.agent_registry import router
    if not any(getattr(route,'path','')=='/api/v1/agent-registry' for route in app.routes):app.include_router(router)


def stack(env,tmp_path):
    from test_ddr_runs import payload
    from kestrel.services.ddr_execution import run_once
    http,_,ids,_=env;source,finding,csrf=candidate(env)
    view=saved_view(http,csrf,ids,source)
    task=post(http,'/api/v1/review-work/sources/'+source['id']+'/tasks',csrf,{'assignee_id':ids['lawyer'],'rationale':'Cross-domain retained source task for current named reviewer','request_key':uuid.uuid4().hex})
    assert task.status_code==201,task.text
    answer=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which consent is required on a change of control?','mode':'lexical'})
    assert answer.status_code==201,answer.text
    run=post(http,'/api/v1/ddr/matters/'+ids['matter']+'/runs',csrf,payload(ids,finding).model_dump())
    assert run.status_code==201,run.text
    assert run_once(env[1],checkpoint_root=tmp_path)
    current=http.get('/api/v1/ddr/runs/'+run.json()['id']);assert current.status_code==200,current.text
    assert current.json()['state']=='awaiting_attorney'
    return source,finding,view,task.json(),answer.json(),current.json(),csrf


def test_whole_matter_wall_overrides_combined_admin_legal_role_and_all_surface_types(env,tmp_path,monkeypatch):
    http,sessions,ids,app=env;source,finding,view,task,answer,run,csrf=stack(env,tmp_path);registry_router(app)
    with sessions() as db:
        role=db.scalar(select(m.Role.id).where(m.Role.name=='root_admin'));db.add(m.RoleGrant(account_id=ids['lawyer'],role_id=role));db.commit()
    # Technical toggles grant no content right and cannot countermand the wall.
    assert post(http,'/api/v1/financial/bank-gate?matter_id='+ids['matter'],csrf,{'expected_revision':0,'enabled':True,'rationale':'Enable only the technical matter feature for this isolated negative matrix'}).status_code==200
    from test_financial_workflow import enable_org
    enable_org(http,csrf)
    monkeypatch.setattr('kestrel.adapters.report_export.export',lambda *args:b'isolated readable Word artifact')
    assert http.get('/api/v1/reports/'+run['report_id']+'/download/docx').status_code==200
    assert post(http,'/api/v1/tables/inventory/query',csrf,{'matter_id':ids['matter'],'saved_view_id':view['id'],'saved_view_version_hash':view['version_hash']}).status_code==200
    wall(sessions,ids['lawyer'],ids['matter'])
    paths=[BASE+'/documents/'+source['id'],BASE+'/documents/'+source['id']+'/reader',BASE+'/documents/'+source['id']+'/download',BASE+'/documents?matter_id='+ids['matter'],BASE+'/findings?matter_id='+ids['matter'],
        '/api/v1/readers/candidates?matter_id='+ids['matter']+'&kind=source','/api/v1/review-work/tasks/'+task['id'],'/api/v1/review-work/notifications?matter_id='+ids['matter'],
        '/api/v1/questions/'+answer['id'],'/api/v1/questions?matter_id='+ids['matter'],'/api/v1/reports?matter_id='+ids['matter'],'/api/v1/reports/'+run['report_id']+'/download/docx',
        '/api/v1/ddr/runs/'+run['id'],'/api/v1/ddr/matters/'+ids['matter']+'/runs','/api/v1/ddr/matters/'+ids['matter']+'/evidence-options',
        '/api/v1/table-views/'+view['id'],'/api/v1/table-views?matter_id='+ids['matter']+'&dataset=inventory','/api/v1/agent-registry?matter_id='+ids['matter'],
        '/api/v1/intelligence/profiles?matter_id='+ids['matter'],'/api/v1/intelligence/alerts?matter_id='+ids['matter']]
    for path in paths:withheld(http.get(path),source['file_name'],'prior written consent','Cross-domain private filter metadata')
    commands=[('/api/v1/tables/inventory/query',{'matter_id':ids['matter'],'saved_view_id':view['id']}),('/api/v1/tables/financial/query',{'matter_id':ids['matter']}),
        ('/api/v1/tables/inventory/export',{'matter_id':ids['matter'],'ids':[source['id']],'format':'csv'}),('/api/v1/intelligence/query',{'matter_id':ids['matter'],'view':'workstream'}),
        ('/api/v1/intelligence/query',{'matter_id':ids['matter'],'view':'financial'}),('/api/v1/questions',{'matter_id':ids['matter'],'question':'Which consent is required?','mode':'lexical'}),
        ('/api/v1/financial/query',{'matter_id':ids['matter']}),('/api/v1/readers/compare',{'matter_id':ids['matter'],'targets':[{'kind':'source','id':source['id']},{'kind':'source','id':str(uuid.uuid4())}]})]
    for path,body in commands:withheld(post(http,path,csrf,body),source['file_name'],'prior written consent')
    with sessions() as db:
        denials=list(db.scalars(select(m.AuditEvent).where(m.AuditEvent.actor_id==ids['lawyer'],m.AuditEvent.outcome=='denied',m.AuditEvent.category=='access')))
        assert len(denials)>=3 and any(row.action.startswith('table.') for row in denials)
        assert all(row.object_id is None for row in denials)


def test_client_person_wall_closes_both_assigned_matters_including_zero_ref_private_views(env):
    from test_wall_checker import setup,propose,approve
    http,_,ids,_=env;setup(env);csrf=login(http).json()['csrf_token'];sources=[];views=[]
    for matter,key in [(ids['matter'],'CROSS-A'),(ids['other'],'CROSS-B')]:
        response=upload(http,csrf,matter,logical_key=key,file_name=key+'.txt');assert response.status_code==201,response.text;sources.append(response.json())
        response=post(http,'/api/v1/table-views',csrf,{'matter_id':matter,'dataset':'inventory','name':key+' private no-row-match query','query':{'matter_id':matter,'search':'unmatched private words'},'rationale':'Private text remains matter-scoped even when its query matches no authorized row','request_key':uuid.uuid4().hex})
        assert response.status_code==201,response.text;views.append(response.json())
    root=login(http,'root').json()['csrf_token'];control=propose(http,root);approve(http,control)
    csrf=login(http).json()['csrf_token']
    for source,view in zip(sources,views):
        withheld(http.get(BASE+'/documents/'+source['id']+'/reader'),source['file_name'])
        withheld(http.get('/api/v1/table-views/'+view['id']),view['name'])
        withheld(post(http,'/api/v1/tables/inventory/query',csrf,{'matter_id':source['matter_id']}),source['file_name'])
        withheld(post(http,'/api/v1/intelligence/query',csrf,{'matter_id':source['matter_id'],'view':'topic'}),source['file_name'])


def test_unassigned_foreign_resources_never_enter_counts_selected_exports_or_tasks(env):
    from kestrel.services.auth import clock
    from test_financial_workflow import source,payload,F
    http,sessions,ids,_=env;own,csrf=source(env);own_fact=post(http,F+'/facts',csrf,payload(own['id'])).json()
    with sessions() as db:db.add(m.MatterAssignment(account_id=ids['sme'],matter_id=ids['other'],expires_at=clock()+3600));db.commit()
    token=login(http,'sme').json()['csrf_token'];foreign=upload(http,token,ids['other'],logical_key='FOREIGN-PRIVATE',file_name='FOREIGN-MATTER-CANARY.txt').json()
    csrf=login(http).json()['csrf_token']
    page=post(http,'/api/v1/tables/inventory/query',csrf,{'matter_id':ids['matter'],'column_filters':{'id':foreign['id']}})
    assert page.status_code==200 and page.json()['recordsFiltered']==0 and page.json()['recordsTotal']==1
    exported=post(http,'/api/v1/tables/inventory/export',csrf,{'matter_id':ids['matter'],'ids':[own['id'],foreign['id']],'format':'csv'})
    assert exported.status_code==200 and exported.headers['x-export-unavailable-count']=='1'
    assert foreign['id'] not in exported.text and foreign['file_name'] not in exported.text
    withheld(http.get(BASE+'/documents/'+foreign['id']+'/reader'),foreign['file_name'])
    withheld(post(http,'/api/v1/review-work/sources/'+foreign['id']+'/tasks',csrf,{'assignee_id':ids['lawyer'],'rationale':'Cross-matter assignment must not create a task','request_key':uuid.uuid4().hex}),foreign['file_name'])
    withheld(post(http,F+'/query',csrf,{'matter_id':ids['other']}),foreign['file_name'])
    injected=post(http,F+'/query',csrf,{'matter_id':ids['matter'],'entity':"Vireo' OR 1=1 --"})
    assert injected.status_code==200 and injected.json()['authorized_count']==0 and own_fact['id'] not in injected.text
    with sessions() as db:assert db.scalar(select(func.count()).select_from(m.ReviewTask))==0


def test_provisional_source_restriction_invalidates_nonselected_cached_corpus_and_semantic_groups(env,monkeypatch):
    from kestrel.adapters import embeddings
    from kestrel.services.auth import clock
    http,sessions,ids,_=env;first,_,csrf=candidate(env,cloud_block=False)
    second=upload(http,csrf,ids['matter'],logical_key='CACHED-SECOND',file_name='nonselected-source-canary.txt').json()
    assert post(http,BASE+'/documents/'+second['id']+'/confirm',csrf,{'snapshot_hash':second['snapshot_hash'],'rationale':'Confirm the second synthetic source before bounded cached retrieval'}).status_code==200
    sends=[];monkeypatch.setattr(embeddings,'configuration',lambda:(True,'synthetic-fixture-key-not-a-real-provider'))
    def send(texts):sends.append(len(texts));return [[1.0]+[0.0]*255 for _ in texts],100
    monkeypatch.setattr(embeddings,'send',send)
    answer=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which change of control requires consent?','mode':'semantic','top_k':1,'request_key':uuid.uuid4().hex})
    assert answer.status_code==201,answer.text;cached=answer.json();assert len(cached['citations'])==1
    visible=cached['citations'][0]['object_id'];hidden=next(item for item in [first,second] if item['id']!=visible)
    with sessions() as db:db.add(m.CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600));db.commit()
    restriction=post(http,'/api/v1/content-labels/sources/'+hidden['id'],csrf,{'expected_revision':0,'request_key':uuid.uuid4().hex,'labels':['competitively_sensitive'],'clean_team_scope':'pricing','rationale':'Protective provisional label takes effect before any independent relaxation'})
    assert restriction.status_code==201,restriction.text
    with sessions() as db:
        db.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;db.commit()
        assert db.scalar(select(func.count()).select_from(m.SourceEmbedding).where(m.SourceEmbedding.source_id==hidden['id']))>0
    withheld(http.get('/api/v1/questions/'+cached['id']),hidden['id'],hidden['file_name'])
    current=post(http,'/api/v1/questions',csrf,{'matter_id':ids['matter'],'question':'Which change of control requires consent?','mode':'lexical'})
    assert current.status_code==201,current.text
    assert current.json()['retrieval']['authorized_chunks']==1 and hidden['id'] not in current.text
    count=len(sends)
    for view in ['semantic','hybrid']:
        result=post(http,'/api/v1/intelligence/query',csrf,{'matter_id':ids['matter'],'view':view,'seed_source_id':visible,'search':'consent'})
        assert result.status_code==200,result.text
        assert result.json()['authorized_count']==1 and hidden['id'] not in result.text and hidden['file_name'] not in result.text
        withheld(post(http,'/api/v1/intelligence/query',csrf,{'matter_id':ids['matter'],'view':view,'seed_source_id':hidden['id']}),hidden['file_name'])
    assert len(sends)==count


def test_named_halden_clean_team_rights_do_not_become_general_source_task_ddr_or_bank_access(env):
    from test_named_source_access import setup,G
    http,sessions,ids,app=env;source,_,csrf=setup(env)
    other=upload(http,csrf,ids['matter'],logical_key='UNSHARED-SOURCE',file_name='not-in-named-grant.txt').json()
    assert post(http,'/api/v1/diligence/documents/'+source['id']+'/reviews',csrf,{'expected_revision':0,'title':'Cross-domain named clean-team review','counterparty':'Synthetic counterparty','scope':'financial','coverage_state':'complete','rationale':'Confirm all original passages before exact named-source approval'}).status_code==201
    grant=post(http,G,csrf,{'source_id':source['id'],'username':'client','outside_business':True,'expires_in_days':7,'rationale':'Named synthetic client recipient outside the business for this exact source'})
    assert grant.status_code==201,grant.text;grant=grant.json();sme=login(http,'sme').json()['csrf_token']
    assert post(http,G+'/'+grant['id']+'/approve',sme,{'rationale':'Independent antitrust approval binds this exact source and named recipient'}).status_code==200
    with TestClient(app,base_url='https://client.localhost') as client,TestClient(app,base_url='https://bank.localhost') as bank:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token'];bt=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token']
        headers={'origin':'https://client.localhost','x-csrf-token':token}
        assert client.get(BASE+'/documents/'+source['id']+'/reader').status_code==200
        page=client.post('/api/v1/tables/inventory/query',json={'matter_id':ids['matter']},headers=headers)
        assert page.status_code==200,page.text;assert page.json()['recordsTotal']==1 and other['id'] not in page.text
        withheld(client.get(BASE+'/documents/'+other['id']+'/reader'),other['file_name'])
        for path in ['/api/v1/review-work/sources/'+source['id'],'/api/v1/ddr/matters/'+ids['matter']+'/runs','/api/v1/agent-registry?matter_id='+ids['matter']]:
            if path.startswith('/api/v1/agent-registry'):registry_router(app)
            withheld(client.get(path),source['file_name'])
        withheld(client.post('/api/v1/tables/inventory/export',json={'matter_id':ids['matter'],'ids':[source['id']],'format':'csv'},headers=headers),source['file_name'])
        panes=client.post('/api/v1/readers/compare',json={'matter_id':ids['matter'],'targets':[{'kind':'source','id':source['id']},{'kind':'source','id':other['id']}]},headers=headers)
        assert panes.status_code==200,panes.text;assert panes.json()['panes'][0]['allowed'] and not panes.json()['panes'][1]['allowed'] and other['id'] not in panes.text
        withheld(bank.get(BASE+'/documents/'+source['id']+'/reader'),source['file_name'])
        withheld(bank.post('/api/v1/intelligence/query',json={'matter_id':ids['matter'],'view':'semantic','seed_source_id':source['id']},headers={'origin':'https://bank.localhost','x-csrf-token':bt}),source['file_name'])
        owner=login(http).json()['csrf_token'];current=http.get(BASE+'/documents/'+source['id']).json()
        downgrade=post(http,BASE+'/documents/'+source['id']+'/classification-requests',owner,{'snapshot_hash':current['snapshot_hash'],'classification':'ordinary','resource_type':'contract','rationale':'Requested scope relaxation remains pending independent governed review'})
        assert downgrade.status_code==201,downgrade.text
        assert post(http,BASE+'/classification-requests/'+downgrade.json()['id']+'/approve',owner,{'rationale':'An author cannot approve their own clean-team scope removal'}).status_code==403
        with sessions() as db:
            assert db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,source['id']).policy_id).classification=='clean_team'
            db.scalar(select(m.CleanTeamMembership).where(m.CleanTeamMembership.account_id==ids['client'])).revoked=True;db.commit()
            assert db.get(m.SourceAccessGrant,grant['id']).state=='approved'
        withheld(client.get(BASE+'/documents/'+source['id']+'/reader'),source['file_name'])
        empty=client.post('/api/v1/tables/inventory/query',json={'matter_id':ids['matter']},headers=headers)
        assert empty.status_code==200 and empty.json()['recordsTotal']==0 and source['id'] not in empty.text


def test_source_label_change_invalidates_bank_fact_tables_clusters_cached_answers_and_saved_views(env,monkeypatch):
    import test_document_workflow as documents,test_disclosures as disclosure
    from test_financial_workflow import TEXT,payload,decision,enable_org
    content=documents.TEXT+' '+TEXT;monkeypatch.setattr(documents,'TEXT',content);monkeypatch.setattr(disclosure,'TEXT',content)
    http,sessions,ids,app=env;source,plan,artifact,csrf=disclosure.prepared(env)
    sme=login(http,'sme').json()['csrf_token']
    assert post(http,disclosure.D+'/artifacts/'+artifact['id']+'/decisions',sme,{'operation':'legal_approve','bundle_hash':artifact['bundle_hash'],'rationale':'Independently release exact synthetic sanitized financial transcript'}).status_code==200
    csrf=login(http).json()['csrf_token'];body=http.get(disclosure.D+'/artifacts/'+artifact['id']+'/reader').json()['units'][0]['text']
    fact=post(http,'/api/v1/financial/facts',csrf,payload(artifact['id'],body,'derivative'));assert fact.status_code==201,fact.text;fact=fact.json()
    sme=login(http,'sme').json()['csrf_token'];assert decision(http,sme,fact,'verify').status_code==200;assert decision(http,sme,fact,'release').status_code==200
    root=login(http,'root').json()['csrf_token'];assert post(http,'/api/v1/financial/bank-gate?matter_id='+ids['matter'],root,{'expected_revision':0,'enabled':True,'rationale':'Feature gate never substitutes for exact artifact and fact release'}).status_code==200;enable_org(http,root)
    with TestClient(app,base_url='https://bank.localhost') as bank:
        token=login(bank,'bank',origin='https://bank.localhost').json()['csrf_token'];headers={'origin':'https://bank.localhost','x-csrf-token':token}
        def command(path,body):return bank.post(path,json=body,headers=headers)
        table_body={'matter_id':ids['matter'],'financial_filters':{'currency':'EUR'}}
        before=command('/api/v1/tables/financial/query',table_body);assert before.status_code==200,before.text;assert before.json()['recordsTotal']==1
        cluster=command('/api/v1/intelligence/query',{'matter_id':ids['matter'],'view':'financial'});assert cluster.status_code==200 and cluster.json()['authorized_count']==1
        answer=command('/api/v1/questions',{'matter_id':ids['matter'],'question':'Show the released revenue evidence','mode':'financial','financial_filters':{'currency':'EUR'}})
        assert answer.status_code==201,answer.text;answer=answer.json();assert answer['citations'][0]['reader']['kind']=='disclosure'
        view=command('/api/v1/table-views',{'matter_id':ids['matter'],'dataset':'financial','name':'Private released revenue configuration','query':table_body,'handling':'source_bound','evidence_refs':[{'kind':'financial','id':fact['id']}],'rationale':'Bank private view is bound to the independently released derivative fact','request_key':uuid.uuid4().hex})
        assert view.status_code==201,view.text;view=view.json()
        for response in [before,cluster,bank.get('/api/v1/questions/'+answer['id']),bank.get('/api/v1/table-views/'+view['id'])]:assert source['id'] not in response.text
        withheld(bank.get(BASE+'/documents/'+source['id']+'/reader'),source['file_name'])
        csrf=login(http).json()['csrf_token']
        changed=post(http,'/api/v1/content-labels/sources/'+source['id'],csrf,{'expected_revision':0,'request_key':uuid.uuid4().hex,'labels':['financial'],'rationale':'New source attributes require separately reviewed replacement release snapshots'})
        assert changed.status_code==201,changed.text
        after=command('/api/v1/tables/financial/query',table_body);assert after.status_code==200,after.text;assert after.json()['recordsTotal']==0 and fact['id'] not in after.text
        after=command('/api/v1/intelligence/query',{'matter_id':ids['matter'],'view':'financial'});assert after.status_code==200 and after.json()['authorized_count']==0 and after.json()['groups']==[]
        withheld(bank.get('/api/v1/questions/'+answer['id']),source['id'],fact['amount_text'])
        withheld(bank.get('/api/v1/table-views/'+view['id']),view['name'])
        panes=command('/api/v1/readers/compare',{'matter_id':ids['matter'],'targets':[{'kind':'source','id':source['id']},{'kind':'derivative','id':artifact['id']}]})
        assert panes.status_code==200,panes.text;assert all(not item['allowed'] for item in panes.json()['panes'])
        assert source['id'] not in panes.text and fact['amount_text'] not in panes.text
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.ContentLabelImpact))>0
        assert {row.operation for row in db.scalars(select(m.FinancialFactDecision).where(m.FinancialFactDecision.fact_id==fact['id']))}=={'verify','release'}
        assert db.scalar(select(func.count()).select_from(m.DisclosureDecision).where(m.DisclosureDecision.artifact_id==artifact['id'],m.DisclosureDecision.operation=='legal_approve'))==1


def test_signing_seals_new_domains_but_retains_read_revocation_hold_and_separate_client_copy_deletion(env,tmp_path):
    import json
    from test_agent_registry import publish,definition
    from test_intelligence_governance import profile
    from test_financial_converters import eml,memberships,upload as upload_email
    from test_lifecycle import propose,approve
    from test_auth_policy import PASSWORD
    from kestrel.bootstrap import provision
    from kestrel.services.auth import clock
    from test_ddr_runs import payload
    http,sessions,ids,app=env;source,finding,view,task,answer,run,csrf=stack(env,tmp_path);registry_router(app)
    agent=publish(env);scoring=profile(env)
    with sessions() as db:
        recipient=provision(db,'cross-domain-recipient','firm',['firm_lawyer'],PASSWORD)
        db.add(m.MatterAssignment(account_id=recipient.id,matter_id=ids['matter'],expires_at=clock()+3600));db.commit();recipient_id=recipient.id
    csrf=login(http).json()['csrf_token']
    share=post(http,'/api/v1/table-views/'+view['id']+'/share-requests',csrf,{'version_hash':view['version_hash'],'recipient_ids':[recipient_id],'expires_in_days':1,'rationale':'Exact same-organization named scope for controlled cross-domain freeze regression','request_key':uuid.uuid4().hex})
    assert share.status_code==201,share.text;share=share.json();sme=login(http,'sme').json()['csrf_token']
    assert post(http,'/api/v1/table-views/share-requests/'+share['id']+'/decisions',sme,{'operation':'approve','content_hash':share['content_hash'],'content_reviewed':True,'rationale':'Independent nonrecipient SME reviewed exact configuration, source scope and named recipient'}).status_code==200
    memberships(sessions,ids,[ids['lawyer'],ids['sme']]);csrf=login(http).json()['csrf_token']
    email_bytes=eml();email=upload_email(http,csrf,ids,'retention.eml',email_bytes,'clean_team','pricing');assert email.status_code==201,email.text;email=email.json()
    assert post(http,BASE+'/documents/'+email['id']+'/confirm',csrf,{'snapshot_hash':email['snapshot_hash'],'rationale':'Confirm entire retained email and staged attachment restrictions'}).status_code==200
    assert post(http,'/api/v1/ddr/runs/'+run['id']+'/cancel',csrf,{'rationale':'Stop queued graph continuation before proposing the signing snapshot'}).status_code==200
    client_bytes=b'Synthetic retained firm record copied from a client-owned collaboration upload.'
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        submission=client.post('/api/v1/client-uploads',params={'matter_id':ids['matter'],'file_name':'retained-client-copy.txt','synthetic':True},content=client_bytes,headers={'origin':'https://client.localhost','x-csrf-token':token,'content-type':'application/octet-stream'})
        assert submission.status_code==201,submission.text;submission=submission.json()
        accepted=post(http,'/api/v1/client-uploads/'+submission['id']+'/accept',csrf,{'logical_key':'RETAINED-CLIENT-COPY','rationale':'Explicit separate firm source copy must survive later client-copy deletion'})
        assert accepted.status_code==201,accepted.text;firm_copy=accepted.json()
        signing=propose(http,ids,'sign')
        with sessions() as db:
            original=json.loads(db.get(m.LifecycleDecision,signing['id']).payload_json)
            for key in ['table_view_versions','table_view_shares','table_view_share_decisions','intelligence_profiles','agent_profiles','agent_profile_versions','ddr_runs','ddr_evidence','ddr_artifacts','ddr_tasks','ddr_report_links']:assert original[key],key
        assert approve(http,signing).status_code==200
        csrf=login(http).json()['csrf_token']
        assert http.get(BASE+'/documents/'+source['id']+'/reader').status_code==200
        assert http.get(BASE+'/documents/'+email['id']+'/attachments/1/download').status_code==200
        assert upload(http,csrf,ids['matter'],logical_key='AFTER-CROSS-DOMAIN-SIGN').status_code==409
        assert post(http,'/api/v1/content-labels/sources/'+source['id'],csrf,{'expected_revision':0,'request_key':uuid.uuid4().hex,'labels':['financial'],'rationale':'Frozen source assertions cannot be modified by a graph or reviewer'}).status_code==409
        new_run=payload(ids,finding).model_dump();new_run['request_key']=uuid.uuid4().hex
        assert post(http,'/api/v1/ddr/matters/'+ids['matter']+'/runs',csrf,new_run).status_code==409
        assert post(http,'/api/v1/table-views',csrf,{'matter_id':ids['matter'],'dataset':'inventory','name':'Blocked post-signing configuration','query':{'matter_id':ids['matter']},'rationale':'No new saved content after immutable signing snapshot','request_key':uuid.uuid4().hex}).status_code==409
        root=login(http,'root').json()['csrf_token']
        assert post(http,'/api/v1/agent-registry/profiles/'+agent['profile_id']+'/versions',root,{'definition':definition(prompt='Changed retained instruction after signing must not be published or staged.'),'expected_version_hash':agent['content_hash'],'rationale':'No post-signing agent configuration content changes','request_key':uuid.uuid4().hex}).status_code==409
        assert post(http,'/api/v1/intelligence/profiles',root,{'matter_id':ids['matter'],'name':'Blocked post-signing scoring','expected_previous_version':0,'recipient_ids':[ids['lawyer']],'assignee_id':ids['lawyer'],'rationale':'No post-signing scoring profile content changes','request_key':uuid.uuid4().hex}).status_code==409
        csrf=login(http).json()['csrf_token']
        assert post(http,'/api/v1/table-views/share-requests/'+share['id']+'/decisions',csrf,{'operation':'revoke','content_hash':share['content_hash'],'content_reviewed':False,'rationale':'Tighten future named configuration access after signing without erasing approvals'}).status_code==200
        hold=propose(http,ids,'hold');assert approve(http,hold).status_code==200
        closing=propose(http,ids,'close');assert approve(http,closing).status_code==200
        assert client.get('/api/v1/client-uploads/'+submission['id']+'/download').status_code==403
        deletion=propose(http,ids,'delete_client_copies');assert approve(http,deletion).status_code==409
        with sessions() as db:assert db.get(m.ClientSubmission,submission['id']).data==client_bytes
        release=propose(http,ids,'release_hold');assert approve(http,release).status_code==200
        assert approve(http,deletion).status_code==200
        with sessions() as db:
            assert db.get(m.ClientSubmission,submission['id']).data is None
            assert db.get(m.SourceVersion,firm_copy['id']).data==client_bytes
            assert db.get(m.SourceVersion,email['id']).data==email_bytes
            assert json.loads(db.get(m.LifecycleDecision,signing['id']).payload_json)==original
            assert db.get(m.AgentProfileVersion,agent['id']).content_hash==agent['content_hash']
            for table in ['table_view_versions','agent_profile_versions','intelligence_profiles','ddr_artifacts']:
                with pytest.raises(DBAPIError) as failure:db.execute(text('DELETE FROM '+table));db.commit()
                message=str(failure.value).casefold()
                assert 'immutable' in message or 'records retained' in message
                db.rollback()
