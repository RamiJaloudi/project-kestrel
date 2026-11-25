import importlib.util,json
from pathlib import Path
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from test_auth_policy import env,login
from test_document_workflow import upload,TEXT
from test_observability_governance import post
from kestrel.models import (LogicalDocument,DocumentVersionLink,SourceVersion,VdrImportBatch,VdrImportRow,DocumentSource,EthicalWall,MatterLifecycle)

BASE='/api/v1/vdr-imports'
CSV='Source ID,VDR Index #,VDR Folder Path,File Name,Doc ID,Assigned Reviewer,Risk Rating,Unknown\n00001,01.02,Contracts,renamed.txt,CONTRACT-001,root,High,extra\n'


def profile(http,csrf,matter,**changes):
    p={'matter_id':matter,'name':'Synthetic vendor map','source_system':'Synthetic VDR','columns':{
        'source_external_id':'Source ID','vdr_index':'VDR Index #','folder_path':'VDR Folder Path','file_name':'File Name',
        'doc_id':'Doc ID','assigned_reviewer':'Assigned Reviewer','risk_rating':'Risk Rating'},**changes}
    return post(http,BASE+'/profiles',csrf,p)


def stage(http,csrf,pid,csv=CSV,key='repeat-import-001',wave='wave1'):
    return post(http,BASE+'/batches',csrf,{'profile_id':pid,'file_name':'synthetic.csv','csv_text':csv,'request_key':key,'wave':wave,'synthetic':True})


def test_identity_versions_same_binary_and_matter_scope(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    one=upload(http,csrf,ids['matter']).json()
    assert post(http,'/api/v1/workflow/documents/'+one['id']+'/confirm',csrf,{'snapshot_hash':one['snapshot_hash'],'rationale':'Human confirmed source classification'}).status_code==200
    two=upload(http,csrf,ids['matter'],logical_key='DIFFERENT-INSTRUMENT').json()
    newer=upload(http,csrf,ids['matter'],previous_id=one['id'],file_name='renamed.txt').json()
    assert one['document_id']==newer['document_id']!=two['document_id']
    assert one['id']!=newer['id'] and one['bytes_hash']==two['bytes_hash']
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(LogicalDocument))==2
        assert db.scalar(select(func.count()).select_from(DocumentVersionLink))==3
    assert http.get('/api/v1/workflow/documents/'+one['id']+'/reader?historical=true').status_code==200
    assert upload(http,csrf,ids['other']).status_code==403


def test_staged_metadata_mapping_replay_and_version_linking(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    p=profile(http,csrf,ids['matter']);assert p.status_code==201,p.text
    pid=p.json()['id'];assert profile(http,csrf,ids['matter']).json()['id']==pid
    preview=stage(http,csrf,pid);assert preview.status_code==201,preview.text
    b=preview.json();row=b['rows'][0]
    assert row['mapped']['source_external_id']=='00001' and row['state']=='ready'
    assert stage(http,csrf,pid).json()['id']==b['id']
    assert stage(http,csrf,pid,csv=CSV+'other').status_code==409
    assert upload(http,csrf,ids['matter'],file_name='wrong.txt',import_row_id=row['id']).status_code==409
    one=upload(http,csrf,ids['matter'],file_name='renamed.txt',import_row_id=row['id'])
    assert one.status_code==201,one.text
    again=upload(http,csrf,ids['matter'],file_name='renamed.txt',import_row_id=row['id'])
    assert again.json()['id']==one.json()['id']
    # New batch carrying the same source bytes adds provenance, not a duplicate version.
    b2=stage(http,csrf,pid,key='repeat-import-002').json()
    assert upload(http,csrf,ids['matter'],file_name='renamed.txt',import_row_id=b2['rows'][0]['id']).json()['id']==one.json()['id']
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(SourceVersion))==1
        assert db.scalar(select(func.count()).select_from(DocumentSource))==2
        assert not db.get(SourceVersion,one.json()['id']).data is None
        assert db.scalar(select(VdrImportRow)).raw_json.find('extra')>=0
    assert http.get(BASE+'/batches/'+b['id']).json()['rows'][0]['state']=='linked'


def test_vdr_new_wave_retains_prior_source_and_review(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    pid=profile(http,csrf,ids['matter']).json()['id']
    b=stage(http,csrf,pid).json();rid=b['rows'][0]['id']
    one=upload(http,csrf,ids['matter'],file_name='renamed.txt',import_row_id=rid).json()
    assert post(http,'/api/v1/workflow/documents/'+one['id']+'/confirm',csrf,{'snapshot_hash':one['snapshot_hash'],'rationale':'Human confirmed source classification'}).status_code==200
    b2=stage(http,csrf,pid,key='wave-two-batch',wave='wave2').json()
    params={'matter_id':ids['matter'],'file_name':'renamed.txt','logical_key':'CONTRACT-001','classification':'ordinary','synthetic':True,
        'wave':'wave2','previous_id':one['id'],'import_row_id':b2['rows'][0]['id']}
    result=http.post('/api/v1/workflow/documents',params=params,content=(TEXT+' Second wave.').encode(),headers={'origin':'https://firm.localhost','x-csrf-token':csrf,'content-type':'application/octet-stream'})
    assert result.status_code==201,result.text
    two=result.json();assert two['document_id']==one['document_id'] and two['version_number']==2
    assert http.get('/api/v1/workflow/documents/'+one['id']+'/reader?historical=true').json()['bytes_hash']==one['bytes_hash']


def test_vdr_quarantine_and_governance_cannot_be_imported(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    p=profile(http,csrf,ids['matter']).json()
    invalid=CSV.replace('renamed.txt','../escape.txt')
    b=stage(http,csrf,p['id'],csv=invalid).json();r=b['rows'][0]
    assert r['state']=='quarantined' and 'UNSAFE_FILE_NAME' in r['errors']
    assert upload(http,csrf,ids['matter'],file_name='renamed.txt',import_row_id=r['id']).status_code==409
    bad=dict(p['columns'],classification_confirmed='Unknown')
    assert profile(http,csrf,ids['matter'],columns=bad).status_code==422
    duplicate=stage(http,csrf,p['id'],csv=CSV+CSV.splitlines()[1]+'\n',key='duplicate-row-key').json()
    assert duplicate['rows'][1]['state']=='quarantined'
    # A stale writer may not silently overwrite a mapping version.
    assert profile(http,csrf,ids['matter'],delimiter=';').status_code==409
    updated=profile(http,csrf,ids['matter'],delimiter=';',expected_previous_version=1)
    assert updated.status_code==201 and updated.json()['version_number']==2
    with sessions() as db:
        for table in ['vdr_import_rows','vdr_import_batches','vdr_mapping_profiles']:
            with pytest.raises(DBAPIError):db.execute(text('DELETE FROM '+table));db.commit()
            db.rollback()


def test_vdr_walls_owner_admin_and_freeze(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token']
    pid=profile(http,csrf,ids['matter']).json()['id'];b=stage(http,csrf,pid).json()
    login(http,'sme');assert http.get(BASE+'/batches/'+b['id']).status_code==403
    csrf=login(http,'root').json()['csrf_token'];assert profile(http,csrf,ids['matter']).status_code==403
    csrf=login(http).json()['csrf_token']
    with sessions() as db:db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    assert http.get(BASE+'/batches/'+b['id']).status_code==403
    assert stage(http,csrf,pid,key='walled-batch-key').status_code==403
    # Separate SME has membership but frozen state still blocks even creating a mapping.
    csrf=login(http,'sme').json()['csrf_token']
    with sessions() as db:db.add(MatterLifecycle(matter_id=ids['matter'],frozen=True));db.commit()
    assert profile(http,csrf,ids['matter'],name='Frozen mapping').status_code==409


def test_additive_backfill_is_repeatable_without_rewriting_sources(env):
    http,sessions,ids,_=env;csrf=login(http).json()['csrf_token'];source=upload(http,csrf,ids['matter']).json()
    p=Path(__file__).resolve().parents[1]/'migrations/versions/0026_document_identity_vdr.py'
    spec=importlib.util.spec_from_file_location('identity_backfill',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with sessions() as db:
        before=db.get(SourceVersion,source['id']).data
        module.backfill(db.connection());module.backfill(db.connection());db.commit()
        assert db.scalar(select(func.count()).select_from(LogicalDocument))==1
        assert db.scalar(select(func.count()).select_from(DocumentVersionLink))==1
        assert db.get(SourceVersion,source['id']).data==before
