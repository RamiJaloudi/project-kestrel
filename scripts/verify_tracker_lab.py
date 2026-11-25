"""Explicit local HTTPS Excel import, audience approval and recipient denial check."""
import io,json,sys,urllib.error,urllib.request
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from kestrel.localenv import read_env
from local_api import LocalAPI
from seed_tracker_lab import examples


def main():
    marker=ROOT/'.runtime/tracker-lab.json';lab=json.loads(marker.read_text(encoding='utf-8'))
    if not lab.get('seeded'):raise RuntimeError('Isolated lab required')
    if lab.get('verified'):print('Tracker lab already verified; existing decisions preserved.');return
    values=read_env();password=values['KESTREL_DUMMY_PASSWORD'];apis=[]
    def client(host,name):api=LocalAPI(host,name,password);apis.append(api);return api
    try:
        lawyer=client('firm.localhost','lawyer01@freshfields.example');sme=client('firm.localhost','sme01@freshfields.example')
        path=Path(lab['local_folder'])/'tracker_next_updates.xlsx'
        query=urlencode({'matter_id':lab['matter_id'],'register':'risk','file_name':path.name,'synthetic':'true'})
        preview=lawyer.call('/api/v1/trackers/imports?'+query,binary=path.read_bytes());assert preview['rows'][0]['status']=='valid'
        payload={'row_numbers':[2],'rationale':'Scripted synthetic HTTPS validation of reviewed tracker updates','attest_reviewed':True,'idempotency_key':'tracker-lab-apply-001'}
        applied=lawyer.call('/api/v1/trackers/imports/'+preview['id']+'/apply',payload);assert applied['applied_rows']==1
        assert lawyer.call('/api/v1/trackers/imports/'+preview['id']+'/apply',payload)==applied
        bank=lawyer.call('/api/v1/trackers/exports',{'matter_id':lab['matter_id'],'register':'risk','audience':'castlegate','recipient_upn':'bank01@castlegate.example','title':'Synthetic bank consent tracker','record_ids':[lab['record_ids']['consent']],'row_edits':{lab['record_ids']['consent']:{'Summary':'Customer consent is required before the proposed control change.','Action':'Confirm consent status with the transaction team.'}}})
        sme.call('/api/v1/workflow/releases/'+bank['release_id']+'/approve',{'content_hash':bank['content_hash'],'snapshot_hash':bank['snapshot_hash'],'rationale':'Independent scripted approval of this exact bank recipient workbook'})
        recipient=client('bank.localhost','bank01@castlegate.example');other=client('bank.localhost','bank02@castlegate.example')
        request=urllib.request.Request(recipient.base+'/api/v1/trackers/exports/'+bank['id']+'/download')
        with recipient.opener.open(request,timeout=20) as response:data=response.read();assert data.startswith(b'PK')
        try:other.call('/api/v1/trackers/exports/'+bank['id']);raise RuntimeError('Other bank recipient unexpectedly received the workbook')
        except urllib.error.HTTPError as error:assert error.code==403
        halden=lawyer.call('/api/v1/trackers/exports',{'matter_id':lab['matter_id'],'register':'risk','audience':'halden','recipient_upn':'client01@halden.example','title':'Synthetic Halden reviewed risk tracker','record_ids':list(lab['record_ids'].values())})
        records={r['id']:r for r in lawyer.call('/api/v1/diligence/board?matter_id='+lab['matter_id'])['risks']}
        examples(lab,{k:records[v] for k,v in lab['record_ids'].items()})
        lab.update(verified=True,verified_import_id=preview['id'],bank_export_id=bank['id'],halden_draft_id=halden['id'])
        marker.write_text(json.dumps(lab,indent=2),encoding='utf-8')
        print('PASS: live XLSX preview/apply/idempotence, independent bank release, approved download and denial to the other bank user. Halden draft and fresh local proposals remain for testing.')
    finally:
        for api in apis:
            try:api.close()
            except Exception:pass


if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('tracker_lab.verification_failed',component='verification',exception=error);print('Tracker verification requires manual review; sanitized diagnostic '+event['event_id']);sys.exit(1)
