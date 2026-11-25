"""One-time isolated synthetic tracker records and local Excel proposals."""
import json,sys
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from local_api import LocalAPI
from kestrel.localenv import read_env
from kestrel.adapters.tracker_workbooks import build
from kestrel.services.trackers import HEADERS
from seed_action_center_lab import publish


def examples(lab,records):
    folder=ROOT.parent/'Synthetic_Data/Tracker_Lab';folder.mkdir(parents=True,exist_ok=True)
    def row(key,date='2026-12-01'):
        record=records[key]
        action='Obtain and record written consent before signing'
        if record['revision']>=2:
            action='Confirm the consent response and record satisfaction before signing'
            if date=='2026-12-01':date='2026-12-02'
        return [record['id'],record['revision'],'high','material','consent','in_progress',action,'lawyer01@freshfields.example',date]
    guide=[['Field','Instructions'],['Matter','054323-100001. Synthetic tracker lab.'],['Records','Keep RecordID / ExpectedRevision. Amber columns are proposals.'],['Apply','Select this matter in Diligence Trackers, open Excel exchange, upload and inspect the preview.'],['Validation','The examples include a valid row, invalid date, duplicate IDs and an unavailable record. No database changes happen during preview.'],['Review','Apply only rows you have reviewed. Any source/finding change requires a fresh audience export.']]
    valid={'sheets':[{'name':'Records','rows':[HEADERS['risk'],row('consent')],'editable':HEADERS['risk'][2:]},{'name':'Guide','rows':guide}]}
    (folder/'tracker_next_updates.xlsx').write_bytes(build(valid,preview=True))
    rows=[row('consent'),row('advice','2026-99-99'),row('assignment'),row('assignment'),['unavailable-record',0,'high','material','consent','open','Check source context','','']]
    (folder/'tracker_validation_examples.xlsx').write_bytes(build({'sheets':[{'name':'Records','rows':[HEADERS['risk'],*rows],'editable':HEADERS['risk'][2:]},{'name':'Guide','rows':guide}]}))
    return folder


def main():
    marker=ROOT/'.runtime/tracker-lab.json'
    if marker.exists():print('Tracker lab already initialized; records, import decisions and releases preserved.');return
    settings=read_env();password=settings['KESTREL_DUMMY_PASSWORD'];owner=settings['KESTREL_RAMI_EMAIL'].casefold();apis=[]
    def client(host,name):
        api=LocalAPI(host,name,password);apis.append(api);return api
    try:
        admin=client('admin.localhost',owner)
        if any(c['client_number']=='054323' for c in admin.call('/api/v1/validation/clients')):
            marker.write_text(json.dumps({'seeded':False,'reason':'Reserved tracker client already exists; no partial fixture replay'}),encoding='utf-8');print('Reserved tracker lab already exists; existing work unchanged.');return
        registry=admin.call('/api/v1/validation/clients',{'name':'Excel tracker workflow lab (synthetic)','client_number':'054323'})
        matter=admin.call('/api/v1/validation/matters',{'client_id':registry['id'],'matter_number':'100001','name':'Tracker import and recipient release lab — synthetic'})['id']
        admin.call('/api/v1/validation/matters/'+matter+'/decision',{'status':'validated','expected_revision':1,'rationale':'Isolated synthetic Excel exchange fixture; main diligence matter excluded'})
        targets=['lawyer01@freshfields.example','sme01@freshfields.example','sme02@freshfields.example','security01@freshfields.example','client01@halden.example','client02@halden.example','bank01@castlegate.example','bank02@castlegate.example',settings['KESTREL_CHRIS_EMAIL'].casefold()]
        for revision,name in enumerate(sorted(set(targets)),2):admin.call('/api/v1/validation/matters/'+matter+'/access',{'username':name,'assigned':True,'blocked':False,'days':365,'expected_revision':revision,'rationale':'One-time synthetic tracker lab assignment only; no existing grants restored'})
        lawyer=client('firm.localhost','lawyer01@freshfields.example');security=client('firm.localhost','security01@freshfields.example')
        publish(admin,security,matter,'Tracker lab approved sharing policy','environment_policy',{'block_ai':True,'block_cloud':True,'block_external':False,'allowed_regions':['OTHER']})
        sources={};records={}
        texts={'contract':'Synthetic customer contract. Assignment and a change of control require prior written consent. Governing law: England and Wales.',
            'advice':'Synthetic privileged internal legal advice for Halden only. Consider a seller indemnity and obtain counsel approval before relying on the proposed risk allocation.'}
        for key,body in texts.items():
            query=urlencode({'matter_id':matter,'file_name':'tracker_lab_'+key+'.txt','logical_key':'TRACKER-LAB-'+key.upper(),'classification':'privileged' if key=='advice' else 'ordinary','resource_type':'legal_advice' if key=='advice' else 'contract','language':'en','governing_law':'England and Wales','wave':'manual','synthetic':'true'})
            source=lawyer.call('/api/v1/workflow/documents?'+query,binary=body.encode())
            lawyer.call('/api/v1/workflow/documents/'+source['id']+'/confirm',{'snapshot_hash':source['snapshot_hash'],'rationale':'Scripted synthetic lab confirms source handling and text'})
            sources[key]=source['id']
        for key,source_key,topic,quote,summary in [
            ('consent','contract','change_of_control','prior written consent','The synthetic customer contract requires consent on a change of control.'),
            ('assignment','contract','assignment','Assignment','The synthetic assignment requirement needs a consent owner and deadline.'),
            ('advice','advice','other','Consider a seller indemnity','Halden-only privileged legal advice on proposed seller indemnity protection.')]:
            record=lawyer.call('/api/v1/diligence/findings',{'source_id':sources[source_key],'expected_revision':0,'decision':'reviewed','summary':summary,'topic':topic,'severity':'high','materiality':'material','exposure':'consent' if key!='advice' else 'unclear','workflow_status':'open','action':'Confirm follow-up with the designated lawyer before signing','owner_id':None,'due_on':'2026-12-01','rationale':'Scripted synthetic lawyer assessment with exact fixture evidence; not real legal advice','evidence':[{'unit':1,'quote':quote}]})
            records[key]=record
        for key,source in sources.items():lawyer.call('/api/v1/diligence/documents/'+source+'/reviews',{'expected_revision':0,'title':'Synthetic '+key+' review','counterparty':'Synthetic Customer' if key=='contract' else 'Halden legal team','scope':'customer' if key=='contract' else 'corporate','coverage_state':'complete','rationale':'Scripted synthetic whole-document review; all fixture findings explicitly reviewed'})
        lab={'seeded':True,'matter_id':matter,'client_number':'054323','sources':sources,'record_ids':{k:r['id'] for k,r in records.items()}}
        folder=examples(lab,records);lab['local_folder']=str(folder)
        marker.write_text(json.dumps(lab,indent=2),encoding='utf-8')
        print('Tracker lab ready: ordinary and privileged reviewed records, coverage and local proposal workbooks. No import applied or audience export released.')
    finally:
        for api in apis:
            try:api.close()
            except Exception:pass


if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('tracker_lab.failed',component='provisioning',exception=error);print('Tracker fixture requires manual review; sanitized diagnostic '+event['event_id']);sys.exit(1)
