import json
from pathlib import Path
from sqlalchemy import select,func
from test_auth_policy import env,login
from test_observability_governance import post
from test_document_workflow import allow_processing,BASE
from kestrel.adapters import provider_secrets,ocr
from kestrel.services import ocr_jobs
from kestrel.models import SourceVersion

def test_provider_key_is_admin_only_write_only_and_not_plaintext(env,monkeypatch,tmp_path):
    http,_,ids,_=env
    monkeypatch.setattr(provider_secrets,'FILE',tmp_path/'provider.json')
    monkeypatch.setattr(provider_secrets,'crypt',lambda data,protect:bytes(b^123 for b in data))
    csrf=login(http,'lawyer').json()['csrf_token'];key='sk-test-only-never-real'
    assert post(http,'/api/v1/ai-provider',csrf,{'api_key':key,'enabled':True}).status_code==403
    csrf=login(http,'root').json()['csrf_token']
    result=post(http,'/api/v1/ai-provider',csrf,{'api_key':key,'enabled':True})
    assert result.status_code==200 and result.json()['key_configured']
    assert key not in result.text and key not in provider_secrets.FILE.read_text()
    assert key not in http.get('/api/v1/ai-provider').text
    post(http,'/api/v1/ai-provider',csrf,{'api_key':'','enabled':False})
    assert provider_secrets.configured()==(False,key)

def prepare_scan(env):
    http,sessions,ids,_=env;allow_processing(http,sessions,ids)
    csrf=login(http,'lawyer').json()['csrf_token']
    path=Path(__file__).resolve().parents[2]/'data/synthetic_waves/Wave_1/S001_v1_scanned_assignment.pdf'
    result=http.post(BASE+'/documents',params={'matter_id':ids['matter'],'file_name':path.name,'logical_key':'SCAN','classification':'ordinary','synthetic':True},content=path.read_bytes(),headers={'origin':'https://firm.localhost','x-csrf-token':csrf,'content-type':'application/octet-stream'})
    row=result.json();assert post(http,BASE+'/documents/'+row['id']+'/confirm',csrf,{'snapshot_hash':row['snapshot_hash'],'rationale':'Human checked declared handling on original scan'}).status_code==200
    return row,csrf
def test_ocr_new_version_human_verification_and_no_admin_override(env,monkeypatch):
    from kestrel.adapters.extraction import canonical,digest
    http,sessions,ids,_=env;source,csrf=prepare_scan(env)
    monkeypatch.setattr(ocr,'available',lambda:True)
    def fake(data,heartbeat=None):
        units=[{'number':1,'locator':'Page 1','text':'Assignment requires prior written consent.','ocr':True,'words':[{'start':0,'end':10,'left':1,'top':1,'width':10,'height':5,'confidence':92}]}]
        return {'units':units,'bytes_hash':digest(data),'text_hash':digest(canonical(units).encode()),'media_type':'application/pdf','extractor':'ocr:fixture','status':'ready'}
    monkeypatch.setattr(ocr,'extract_pdf',fake)
    job=post(http,'/api/v1/ocr/'+source['id'],csrf,{});assert job.status_code==201,job.text
    assert ocr_jobs.run_once(sessions)
    state=http.get('/api/v1/ocr',params={'matter_id':ids['matter']}).json()[0];assert state['state']=='succeeded'
    fresh=http.get(BASE+'/documents/'+state['result_source_id']).json()
    assert fresh['version_number']==2 and fresh['bytes_hash']==source['bytes_hash'] and fresh['extraction_status']=='ocr_review'
    assert post(http,BASE+'/documents/'+fresh['id']+'/confirm',csrf,{'snapshot_hash':fresh['snapshot_hash'],'rationale':'Cannot bypass OCR verification'}).status_code==409
    assert post(http,'/api/v1/ocr/'+fresh['id']+'/verify',csrf,{'text_hash':fresh['text_hash'],'rationale':'Lawyer compared transcript and original page image'}).status_code==200
    fresh=http.get(BASE+'/documents/'+fresh['id']).json();assert fresh['extraction_status']=='ready'
    assert post(http,BASE+'/documents/'+fresh['id']+'/confirm',csrf,{'snapshot_hash':fresh['snapshot_hash'],'rationale':'Confirm handling after verified OCR text'}).status_code==200
    login(http,'root');assert http.get(BASE+'/documents/'+fresh['id']).status_code==403
    with sessions() as db:assert db.scalar(select(func.count()).select_from(SourceVersion))==2
