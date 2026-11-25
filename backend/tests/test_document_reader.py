from pathlib import Path
import pytest
from sqlalchemy import select
from test_auth_policy import env,login
from test_document_workflow import upload,BASE
from kestrel.models import EthicalWall

CORPUS=Path(__file__).resolve().parents[2]/'data/synthetic_waves/Wave_1'

@pytest.mark.parametrize('name,kind',[
    ('C001_v1_customer_contract.pdf','pdf'),
    ('L001_v1_software_licence.docx','word'),
    ('S001_v1_scanned_assignment.pdf','pdf'),
])
def test_reader_formats_and_protected_inline_pdf(env,name,kind):
    http,_,ids,_=env;csrf=login(http,'lawyer').json()['csrf_token']
    result=http.post(BASE+'/documents',params={'matter_id':ids['matter'],'file_name':name,'logical_key':'READER',
        'classification':'ordinary','resource_type':'contract','synthetic':True},content=(CORPUS/name).read_bytes(),
        headers={'origin':'https://firm.localhost','x-csrf-token':csrf,'content-type':'application/octet-stream'})
    assert result.status_code==201,result.text
    source=result.json();path=BASE+'/documents/'+source['id']
    response=http.get(path+'/reader')
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    reader=response.json();assert reader['format']==kind and reader['bytes_hash']==source['bytes_hash']
    assert 'classification_requests' not in reader
    assert reader['units']
    inline=http.get(path+'/inline')
    if kind=='pdf':
        assert inline.status_code==200 and inline.content==(CORPUS/name).read_bytes()
        assert inline.headers['content-type']=='application/pdf'
        assert inline.headers['content-security-policy']=="frame-ancestors 'self'"
        assert inline.headers['x-frame-options']=='SAMEORIGIN'
        assert inline.headers['content-disposition'].startswith('inline;')
        assert inline.headers['cache-control']=='no-store'
        from fastapi.testclient import TestClient
        for host,name in [('client','client'),('bank','bank')]:
            with TestClient(env[3],base_url='https://'+host+'.localhost') as external:
                login(external,name,origin='https://'+host+'.localhost')
                assert external.get(path+'/reader').status_code==403
                assert external.get(path+'/inline').status_code==403
    else:
        assert inline.status_code==415
        assert inline.headers['content-security-policy']=="frame-ancestors 'none'"
        assert any(b['kind']=='paragraph' for b in reader['blocks'])

def test_reader_text_history_and_revoked_wall_access(env):
    http,sessions,ids,_=env;csrf=login(http,'lawyer').json()['csrf_token']
    source=upload(http,csrf,ids['matter']).json();path=BASE+'/documents/'+source['id']
    assert http.get(path+'/reader').json()['format']=='text'
    from test_observability_governance import post
    assert post(http,path+'/confirm',csrf,{'snapshot_hash':source['snapshot_hash'],'rationale':'Confirm original for historical evidence review'}).status_code==200
    assert upload(http,csrf,ids['matter'],previous_id=source['id']).status_code==201
    assert http.get(path+'/reader').status_code==403
    assert http.get(path+'/reader',params={'historical':True}).status_code==200
    login(http,'root');assert http.get(path+'/reader').status_code==403
    login(http,'lawyer')
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
    assert http.get(path+'/reader',params={'historical':True}).status_code==403
    assert http.get(path+'/inline',params={'historical':True}).status_code==403

def test_excel_reader_keeps_sheet_names_coordinates_and_named_scope(env):
    from kestrel.models import CleanTeamMembership
    from kestrel.services.auth import clock
    http,sessions,ids,_=env
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+1000));db.commit()
    csrf=login(http,'lawyer').json()['csrf_token'];name='P001_v1_clean_team_pricing.xlsx'
    result=http.post(BASE+'/documents',params={'matter_id':ids['matter'],'file_name':name,'logical_key':'PRICING',
        'classification':'clean_team','resource_type':'pricing','clean_team_scope':'pricing','synthetic':True},content=(CORPUS/name).read_bytes(),
        headers={'origin':'https://firm.localhost','x-csrf-token':csrf,'content-type':'application/octet-stream'})
    assert result.status_code==201,result.text
    path=BASE+'/documents/'+result.json()['id']
    reader=http.get(path+'/reader').json()
    assert reader['format']=='excel' and reader['sheets'][0]['name']
    cells=[c for r in reader['sheets'][0]['rows'] for c in r['cells']]
    assert any(c['coordinate']=='B3' and c['text']=='120000' for c in cells)
    assert all(r['unit'] for r in reader['sheets'][0]['rows'])
    login(http,'sme');assert http.get(path+'/reader').status_code==403
    login(http,'root');assert http.get(path+'/reader').status_code==403
    with sessions() as db:
        for grant in db.scalars(select(CleanTeamMembership)):grant.revoked=True
        db.commit()
    login(http,'lawyer');assert http.get(path+'/reader').status_code==403
