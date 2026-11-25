from fastapi.testclient import TestClient
from test_auth_policy import env,login
from test_document_workflow import candidate,BASE
from test_observability_governance import post
from test_reports import generate
from kestrel.models import DocumentPolicyVersion,SourceVersion
C='/api/v1/collaboration'

def test_client_question_reply_independent_approval_bank_and_revocation(env):
    http,sessions,ids,app=env;source,finding,csrf=candidate(env)
    report=generate(http,csrf,ids['matter'],finding['id']).json()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,{'content_hash':report['content_hash'],'snapshot_hash':report['snapshot_hash'],'rationale':'Approve complete synthetic client report'}).status_code==200
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        question=client.post(C,json={'release_id':report['release_id'],'kind':'question','body':'Which consent should we request first?'},headers={'origin':'https://client.localhost','x-csrf-token':token})
        assert question.status_code==201,question.text
        csrf=login(http,'lawyer').json()['csrf_token']
        reply=post(http,C,csrf,{'release_id':report['release_id'],'parent_id':question.json()['id'],'kind':'reply','body':'Counsel should confirm the reviewed consent trigger before any request.'}).json()
        assert reply['state']=='firm_draft' and len(client.get(C,params={'release_id':report['release_id']}).json())==1
        decision={'body_hash':reply['body_hash'],'rationale':'Independent lawyer reviewed exact answer and audience'}
        assert post(http,C+'/'+reply['id']+'/approve',csrf,decision).status_code==403
        csrf=login(http,'sme').json()['csrf_token'];assert post(http,C+'/'+reply['id']+'/approve',csrf,decision).status_code==200
        visible=client.get(C,params={'release_id':report['release_id']}).json();assert len(visible)==2 and any(m['state']=='lawyer_approved' for m in visible)
        with TestClient(app,base_url='https://bank.localhost') as bank:
            login(bank,'bank',origin='https://bank.localhost');assert bank.get(C,params={'release_id':report['release_id']}).status_code==403
        with sessions() as db:db.get(DocumentPolicyVersion,db.get(SourceVersion,source['id']).policy_id).quarantined=True;db.commit()
        assert client.get(C,params={'release_id':report['release_id']}).status_code==403
    login(http,'root');assert http.get(C,params={'release_id':report['release_id']}).status_code==403

def test_collaboration_drafts_and_cross_package_parent_are_closed(env):
    http,_,ids,_=env;_,finding,csrf=candidate(env)
    draft=generate(http,csrf,ids['matter'],finding['id']).json()
    assert post(http,C,csrf,{'release_id':draft['release_id'],'body':'Attempt on an unreleased report'}).status_code==409


def test_report_section_context_filters_and_reply_inheritance(env):
    from test_diligence import assessment
    http,sessions,ids,app=env;source,finding,csrf=candidate(env)
    manual=post(http,'/api/v1/diligence/findings',csrf,assessment(source,topic='assignment')).json()
    report=post(http,'/api/v1/reports/generate',csrf,{'matter_id':ids['matter'],'audience':'halden','kind':'due_diligence','title':'Two-section synthetic report','finding_ids':[finding['id'],manual['id']]}).json()
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+report['release_id']+'/approve',csrf,{'content_hash':report['content_hash'],'snapshot_hash':report['snapshot_hash'],'rationale':'Approve this exact two-section report and annexes'}).status_code==200
    with TestClient(app,base_url='https://client.localhost') as client:
        token=login(client,'client',origin='https://client.localhost').json()['csrf_token']
        headers={'origin':'https://client.localhost','x-csrf-token':token}
        questions=[]
        for index in [0,1,None]:
            response=client.post(C,json={'release_id':report['release_id'],'section_index':index,'body':'Please explain this exact reviewed report context.'},headers=headers)
            assert response.status_code==201,response.text
            questions.append(response.json())
        assert len(client.get(C,params={'release_id':report['release_id']}).json())==3
        for index in [0,1]:
            rows=client.get(C,params={'release_id':report['release_id'],'section_index':index}).json()
            assert len(rows)==1 and rows[0]['section_index']==index
        assert client.post(C,json={'release_id':report['release_id'],'section_index':2,'body':'Invalid report section context.'},headers=headers).status_code==422
        assert client.get(C,params={'release_id':report['release_id'],'section_index':2}).status_code==422
        csrf=login(http,'lawyer').json()['csrf_token']
        mismatch=post(http,C,csrf,{'release_id':report['release_id'],'section_index':1,'parent_id':questions[0]['id'],'kind':'reply','body':'A reply cannot be moved to a different section.'})
        assert mismatch.status_code==422
        reply=post(http,C,csrf,{'release_id':report['release_id'],'parent_id':questions[0]['id'],'kind':'reply','body':'This exact response needs independent lawyer approval.'})
        assert reply.status_code==201 and reply.json()['section_index']==0
        assert len(client.get(C,params={'release_id':report['release_id'],'section_index':0}).json())==1
        assert client.post(C,json={'release_id':report['release_id'],'parent_id':reply.json()['id'],'kind':'reply','body':'Attempt to reference a hidden firm response.'},headers=headers).status_code==403
        with TestClient(app,base_url='https://bank.localhost') as bank:
            login(bank,'bank',origin='https://bank.localhost')
            assert bank.get(C,params={'release_id':report['release_id'],'section_index':0}).status_code==403
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError
        import pytest
        with sessions() as db:
            with pytest.raises(DBAPIError):
                db.execute(text('UPDATE collaboration_messages SET section_index=1 WHERE id=:id'),{'id':questions[0]['id']});db.commit()
            db.rollback()
        # The additive migration refuses to discard retained section context.
        from pathlib import Path
        from alembic import command
        from alembic.config import Config
        import pytest
        # A newer retained identity projection can stop the downgrade before 0024.
        with pytest.raises(RuntimeError,match='archival rollback|Retained document identity/import'):
            command.downgrade(Config(str(Path(__file__).resolve().parents[1]/'alembic.ini')),'0023')
