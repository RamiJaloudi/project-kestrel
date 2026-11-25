import io,json
import pytest
from sqlalchemy import select
from test_auth_policy import env,login,PASSWORD
from test_document_workflow import candidate,BASE
from test_observability_governance import post
from kestrel import models as m

API='/api/v1/trackers'


def workbook(rows,headers=None):
    from kestrel.adapters.tracker_workbooks import build
    from kestrel.services.trackers import HEADERS
    return build({'sheets':[{'name':'Records','rows':[headers or HEADERS['risk'],*rows]}]})


def risk_row(finding):
    return [finding['id'],0,'high','material','consent','open','Obtain written consent before signing','','2026-12-01']


def stage(http,csrf,matter,data,kind='risk'):
    return http.post(API+'/imports',params={'matter_id':matter,'register':kind,'file_name':'synthetic.xlsx','synthetic':True},content=data,headers={'origin':'https://firm.localhost','x-csrf-token':csrf,'content-type':'application/octet-stream'})


def test_preview_commit_versions_idempotence_and_staleness(env):
    http,sessions,ids,_=env
    source,finding,csrf=candidate(env)
    original=finding['summary']
    result=stage(http,csrf,ids['matter'],workbook([risk_row(finding)]));assert result.status_code==201,result.text
    preview=result.json();assert preview['rows'][0]['status']=='valid'
    assert http.get(BASE+'/findings',params={'matter_id':ids['matter']}).json()[0]['revision']==0
    payload={'row_numbers':[2],'rationale':'Lawyer checked these proposed tracker changes','attest_reviewed':True,'idempotency_key':'tracker-apply-test-001'}
    saved=post(http,API+'/imports/'+preview['id']+'/apply',csrf,payload);assert saved.status_code==200,saved.text
    assert post(http,API+'/imports/'+preview['id']+'/apply',csrf,payload).status_code==200
    current=http.get(BASE+'/findings',params={'matter_id':ids['matter']}).json()[0]
    assert current['revision']==1 and current['severity']=='high' and current['summary']==original
    unchanged=risk_row(finding);unchanged[1]=1
    same=stage(http,csrf,ids['matter'],workbook([unchanged])).json()
    assert same['rows'][0]['status']=='unchanged'
    assert post(http,API+'/imports/'+same['id']+'/apply',csrf,payload).status_code==409
    stale=stage(http,csrf,ids['matter'],workbook([risk_row(finding)])).json()
    assert stale['rows'][0]['status']=='conflict'
    assert post(http,API+'/imports/'+stale['id']+'/apply',csrf,payload).status_code==409


def test_duplicates_invalid_dates_formulas_and_no_admin_override(env):
    http,sessions,ids,_=env
    _,finding,csrf=candidate(env)
    row=risk_row(finding)
    result=stage(http,csrf,ids['matter'],workbook([row,row])).json()
    assert all(r['status']=='invalid' for r in result['rows'])
    row[-1]='2026-99-99'
    assert stage(http,csrf,ids['matter'],workbook([row])).json()['rows'][0]['status']=='invalid'
    csrf=login(http,'root').json()['csrf_token']
    assert stage(http,csrf,ids['matter'],workbook([risk_row(finding)])).status_code==403


def test_preview_rechecks_permissions_and_cannot_apply_hidden_rows(env):
    http,sessions,ids,_=env
    _,finding,csrf=candidate(env)
    preview=stage(http,csrf,ids['matter'],workbook([risk_row(finding)])).json()
    with sessions() as db:
        db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
    assert http.get(API+'/imports/'+preview['id']).status_code==403
    assert post(http,API+'/imports/'+preview['id']+'/apply',csrf,{'row_numbers':[2],'rationale':'Wall must override this request','attest_reviewed':True,'idempotency_key':'wall-tracker-test'}).status_code==403


def draft_export(env,classification='ordinary'):
    http,sessions,ids,_=env
    _,finding,csrf=candidate(env,classification)
    result=post(http,API+'/exports',csrf,{'matter_id':ids['matter'],'register':'risk','audience':'halden','recipient_upn':'client','title':'Synthetic risk tracker','record_ids':[finding['id']]})
    assert result.status_code==201,result.text
    return result.json(),csrf


def test_recipient_specific_export_approval_revocation_and_no_source_passages(env):
    from fastapi.testclient import TestClient
    from kestrel.bootstrap import provision
    from kestrel.services.auth import clock
    http,sessions,ids,app=env
    export,csrf=draft_export(env)
    assert post(http,BASE+'/releases/'+export['release_id']+'/approve',csrf,{'content_hash':export['content_hash'],'snapshot_hash':export['snapshot_hash'],'rationale':'Self approval must be denied'}).status_code==403
    with TestClient(app,base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        assert client.get(API+'/exports/'+export['id']+'/download').status_code==403
        csrf=login(http,'sme').json()['csrf_token']
        assert post(http,BASE+'/releases/'+export['release_id']+'/approve',csrf,{'content_hash':export['content_hash'],'snapshot_hash':export['snapshot_hash'],'rationale':'Independent audience-specific workbook approval'}).status_code==200
        result=client.get(API+'/exports/'+export['id']+'/download');assert result.status_code==200
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(result.content),read_only=True)
        text=' '.join(str(c.value) for s in book for row in s for c in row if c.value is not None);book.close()
        assert 'prior written consent' not in text and 'source_id' not in text
    with sessions() as db:
        other=provision(db,'other_client','halden',['client_user'],PASSWORD)
        db.add(m.MatterAssignment(account_id=other.id,matter_id=ids['matter'],expires_at=clock()+3600));db.commit()
    with TestClient(app,base_url='https://client.localhost') as other:
        login(other,'other_client',origin='https://client.localhost')
        assert other.get(API+'/exports/'+export['id']+'/download').status_code==403
        assert other.get(BASE+'/releases/'+export['release_id']).status_code==403
    current=http.get(API+'/exports/'+export['id']).json()
    assert post(http,BASE+'/releases/'+export['release_id']+'/revoke',csrf,{'content_hash':current['content_hash'],'snapshot_hash':current['snapshot_hash'],'rationale':'Revoke this exact workbook package'}).status_code==200


def test_bank_privilege_and_source_changes_block_exports(env):
    http,sessions,ids,_=env
    source,finding,csrf=candidate(env,'privileged')
    result=post(http,API+'/exports',csrf,{'matter_id':ids['matter'],'register':'risk','audience':'castlegate','recipient_upn':'bank','title':'Bank tracker must exclude legal advice','record_ids':[finding['id']]})
    assert result.status_code==403


def test_source_change_blocks_previously_approved_recipient_download(env):
    from fastapi.testclient import TestClient
    http,sessions,ids,app=env
    export,_=draft_export(env)
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+export['release_id']+'/approve',csrf,{'content_hash':export['content_hash'],'snapshot_hash':export['snapshot_hash'],'rationale':'Approve exact current source snapshot'}).status_code==200
    with sessions() as db:
        package=db.get(m.ReleasePackage,export['release_id'])
        finding_policy=db.scalar(select(m.PolicySource.source_id).where(m.PolicySource.artifact_id==package.policy_id))
        db.get(m.DocumentPolicyVersion,finding_policy).superseded=True;db.commit()
    with TestClient(app,base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        assert client.get(API+'/exports/'+export['id']+'/download').status_code==403
    assert http.get(API+'/exports/'+export['id']).json()['lineage_stale']


def test_export_rechecks_requester_wall_after_rendering(env,monkeypatch):
    from kestrel.services import trackers
    http,sessions,ids,_=env
    _,finding,csrf=candidate(env)
    build=trackers.build
    def change_access(payload):
        content=build(payload)
        with sessions() as db:
            db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
        return content
    monkeypatch.setattr(trackers,'build',change_access)
    result=post(http,API+'/exports',csrf,{'matter_id':ids['matter'],'register':'risk','audience':'halden','recipient_upn':'client','title':'Revoked during generation','record_ids':[finding['id']]})
    assert result.status_code==403
    with sessions() as db:assert db.scalar(select(m.TrackerExport)) is None


def test_coverage_import_and_atomic_selected_row_failure(env):
    from kestrel.services.trackers import HEADERS
    http,sessions,ids,_=env
    source,finding,csrf=candidate(env)
    rows=[[source['id'],0,'Synthetic customer contract','Synthetic customer','customer','complete']]
    p=stage(http,csrf,ids['matter'],workbook(rows,HEADERS['coverage']),'coverage').json()
    assert p['rows'][0]['status']=='valid'
    assert post(http,API+'/imports/'+p['id']+'/apply',csrf,{'row_numbers':[2],'rationale':'Whole contract and findings reviewed','attest_reviewed':True,'idempotency_key':'coverage-import-test'}).status_code==200
    with sessions() as db:
        assert db.scalar(select(m.DocumentReviewVersion).where(m.DocumentReviewVersion.source_id==source['id'])).coverage_state=='complete'
    malformed=risk_row(finding);malformed[0]='unknown-record'
    p=stage(http,csrf,ids['matter'],workbook([risk_row(finding),malformed])).json()
    assert post(http,API+'/imports/'+p['id']+'/apply',csrf,{'row_numbers':[2,3],'rationale':'Bad row must roll back every selected change','attest_reviewed':True,'idempotency_key':'atomic-import-test'}).status_code==403
    with sessions() as db:
        assert db.scalar(select(m.LegalFindingRevision).where(m.LegalFindingRevision.candidate_id==finding['id'])) is None


def test_formula_hidden_content_and_literal_formula_injection(env):
    import zipfile,xml.etree.ElementTree as ET
    http,sessions,ids,_=env
    _,finding,csrf=candidate(env)
    raw=workbook([risk_row(finding)])
    for mode in ['formula','hidden']:
        output=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as original,zipfile.ZipFile(output,'w') as changed:
            for name in original.namelist():
                content=original.read(name)
                if name=='xl/worksheets/sheet1.xml':
                    root=ET.fromstring(content);ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    if mode=='hidden':root.find('.//s:row',ns).set('hidden','1')
                    else:
                        cell=root.find('.//s:c',ns)
                        for child in list(cell):cell.remove(child)
                        cell.set('t','n');ET.SubElement(cell,'{'+ns['s']+'}f').text='1+1'
                    content=ET.tostring(root)
                changed.writestr(name,content)
        assert stage(http,csrf,ids['matter'],output.getvalue()).status_code==422
    row=risk_row(finding);row[6]='=HYPERLINK("https://example.invalid","unsafe")'
    p=stage(http,csrf,ids['matter'],workbook([row])).json()
    assert p['rows'][0]['status']=='valid' and p['rows'][0]['proposed']['Action']==row[6]


def test_clean_team_export_requires_separate_antitrust_and_freeze_blocks_import(env):
    from kestrel.services.auth import clock
    from kestrel.bootstrap import provision
    http,sessions,ids,_=env
    with sessions() as db:
        anti=provision(db,'antitrust','firm',['antitrust_counsel'],PASSWORD);anti_id=anti.id
        db.add(m.MatterAssignment(account_id=anti_id,matter_id=ids['matter'],expires_at=clock()+3600))
        for account in [ids['lawyer'],ids['sme'],anti_id]:db.add(m.CleanTeamMembership(account_id=account,matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=clock()+3600))
        db.commit()
    export,_=draft_export(env,'clean_team')
    csrf=login(http,'sme').json()['csrf_token']
    reason={'content_hash':export['content_hash'],'snapshot_hash':export['snapshot_hash'],'rationale':'Independent release gate check'}
    assert post(http,BASE+'/releases/'+export['release_id']+'/approve',csrf,reason).status_code==409
    csrf=login(http,'antitrust').json()['csrf_token']
    assert post(http,BASE+'/releases/'+export['release_id']+'/antitrust',csrf,reason).status_code==200
    reason['snapshot_hash']=http.get(API+'/exports/'+export['id']).json()['snapshot_hash']
    csrf=login(http,'sme').json()['csrf_token']
    assert post(http,BASE+'/releases/'+export['release_id']+'/approve',csrf,reason).status_code==200
    with sessions() as db:
        db.add(m.MatterLifecycle(matter_id=ids['matter'],frozen=True));db.commit()
    # Even a cleared lawyer cannot stage new tracker changes after signing.
    csrf=login(http,'lawyer').json()['csrf_token']
    assert stage(http,csrf,ids['matter'],workbook([['unavailable',0,'high','material','consent','open','Check consent','','']])).status_code==409
