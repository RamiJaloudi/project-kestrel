"""Pinned finding metadata and unchanged, source-bound assessment commands."""
import csv,io
import uuid
from test_auth_policy import env,login
from test_document_workflow import upload,BASE
from test_diligence import assessment,D
from test_observability_governance import post

T='/api/v1/tables/findings'


def findings(env):
    h,_,ids,_=env;c=login(h).json()['csrf_token'];src=upload(h,c,ids['matter']).json()
    assert post(h,BASE+'/documents/'+src['id']+'/confirm',c,{'snapshot_hash':src['snapshot_hash'],'rationale':'Confirm synthetic source before exact finding review'}).status_code==200
    rows=[]
    for changes in [{},{'topic':'other','severity':'low','materiality':'not_material','workflow_status':'resolved','exposure':'none'}]:
        r=post(h,D+'/findings',c,assessment(src,**changes));assert r.status_code==201,r.text;rows.append(r.json())
    return src,rows,c


def test_finding_pages_presets_exact_locator_and_allowlists(env):
    h,_,ids,_=env;_,rows,c=findings(env)
    p={'matter_id':ids['matter'],'draw':3,'length':1,'sort':'severity'}
    r=post(h,T+'/query',c,p);assert r.status_code==200,r.text;value=r.json()
    assert value['draw']==3 and value['recordsTotal']==2 and len(value['data'])==1
    assert 'evidence' not in value['data'][0] and 'rationale' not in value['data'][0] and 'ai_contexts' not in value['data'][0]
    r=post(h,T+'/query',c,{**p,'finding_filters':{'register':'consents','status':'active'}})
    assert r.status_code==200 and r.json()['recordsTotal']==1 and r.json()['data'][0]['id']==rows[0]['id'],r.text
    assert post(h,T+'/query',c,{**p,'finding_filters':{'record_key':rows[1]['id']}}).json()['data'][0]['revision_id']==rows[1]['revision_id']
    for extra in [{'sort':'evidence_json'},{'finding_filters':{'register':'SQL'}},{'finding_filters':{'status':'approved'}},{'finding_filters':{'severity':'probably high'}},{'source_filters':{}},{'task_filters':{}},{'financial_filters':{}},{'saved_view_id':str(uuid.uuid4())}]:
        r=post(h,T+'/query',c,{**p,**extra});assert r.status_code==422,r.text
    assert post(h,'/api/v1/tables/tasks/query',c,{'matter_id':ids['matter'],'finding_filters':{}}).status_code==422


def test_exact_detail_rejects_changed_revision_and_retains_independent_editor_commands(env):
    h,_,ids,_=env;src,rows,c=findings(env);row=rows[0]
    params={'matter_id':ids['matter'],'revision_id':row['revision_id']}
    r=h.get(T+'/'+row['id'],params=params);assert r.status_code==200,r.text
    value=r.json();assert value['finding']['revision_id']==row['revision_id'] and value['finding']['evidence'][0]['quote']=='change of control'
    assert isinstance(value['eligible_owners'],list) and value['source_review_available'] is True
    assert value['source']['id']==src['id'] and value['source']['finding_progress']['reviewed']==2
    revised=post(h,D+'/findings/'+row['id']+'/revisions',c,assessment(src,expected_revision=1,summary='An updated exact legal assessment remains an internal finding.'))
    assert revised.status_code==201,revised.text
    r=h.get(T+'/'+row['id'],params=params);assert r.status_code==409 and row['summary'] not in r.text,r.text
    params['revision_id']=revised.json()['revision_id']
    assert h.get(T+'/'+row['id'],params=params).json()['finding']['revision']==2
    assert h.get(T+'/'+row['id'],params={**params,'matter_id':ids['other']}).status_code==403


def test_finding_selected_export_requires_exact_revision_map_and_never_substitutes_latest(env):
    h,_,ids,_=env;src,rows,c=findings(env);row=rows[0]
    p={'matter_id':ids['matter'],'ids':[row['id']],'format':'csv'}
    assert post(h,T+'/export',c,p).status_code==422
    assert post(h,T+'/export',c,{**p,'finding_versions':{str(uuid.uuid4()):row['revision_id']}}).status_code==422
    p['finding_versions']={row['id']:row['revision_id']}
    r=post(h,T+'/export',c,p);assert r.status_code==200,r.text
    assert list(csv.DictReader(io.StringIO(r.text)))[0]['revision_id']==row['revision_id']
    assert 'evidence' not in r.text and 'rationale' not in r.text
    r=post(h,T+'/export',c,{**p,'format':'xlsx'});assert r.status_code==200,r.text
    from openpyxl import load_workbook
    book=load_workbook(io.BytesIO(r.content),data_only=False);assert book.active.max_row==2 and all(cell.data_type!='f' for cells in book.active for cell in cells);book.close()
    r=post(h,D+'/findings/'+row['id']+'/revisions',c,assessment(src,expected_revision=1));assert r.status_code==201,r.text
    r=post(h,T+'/export',c,p);assert r.status_code==200 and r.headers['x-export-unavailable-count']=='1' and row['id'] not in r.text,r.text
    assert post(h,'/api/v1/tables/inventory/export',c,{**p,'ids':[src['id']]}).status_code==422


def test_source_only_profile_is_fresh_and_unproven_legacy_review_is_not_invented(env):
    h,_,ids,_=env;c=login(h).json()['csrf_token'];src=upload(h,c,ids['matter']).json()
    r=h.get(T+'/source-profile/'+src['id'],params={'matter_id':ids['matter']});assert r.status_code==200,r.text
    value=r.json();assert value['source_review_available'] and value['source']['finding_progress']['total']==0
    assert value['source']['document_review']['revision']==0
    assert post(h,D+'/documents/'+src['id']+'/reviews',c,{'expected_revision':0,'title':'Retained private review profile','counterparty':'Synthetic party','scope':'other','coverage_state':'in_review','rationale':'Retain existing document review without inventing historical scope'}).status_code==201
    r=h.get(T+'/source-profile/'+src['id'],params={'matter_id':ids['matter']});assert r.status_code==200,r.text
    assert r.json()['source_review_available'] is True
    assert r.json()['source']['document_review']['metadata_withheld'] is True
    assert r.json()['source']['document_review']['coverage_state']=='unavailable'
    assert r.json()['source']['document_review']['revision']==1
    assert 'Retained private review profile' not in r.text and 'Synthetic party' not in r.text
