"""One-time isolated synthetic wall examples via authenticated, independently scoped accounts."""
import json,sys
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from local_api import LocalAPI
from kestrel.localenv import read_env
CLIENT='054321'
NAME='Ethical wall checker lab (synthetic)'

def main():
    marker=ROOT/'.runtime/wall-checker-lab.json'
    if marker.exists():print('Wall checker lab already initialized; existing decisions and assignments preserved.');return
    settings=read_env();password=settings['KESTREL_DUMMY_PASSWORD'];owner=settings['KESTREL_RAMI_EMAIL'].casefold();apis=[]
    folder=ROOT.parent/'Synthetic_Data/Wall_Checker_Lab';folder.mkdir(parents=True,exist_ok=True)
    try:
        admin=LocalAPI('admin.localhost',owner,password);apis.append(admin)
        clients=admin.call('/api/v1/validation/clients')
        if any(c['client_number']==CLIENT for c in clients):
            marker.write_text(json.dumps({'seeded':False,'reason':'client number already exists; no existing work changed'}),encoding='utf-8');print('Wall checker lab skipped: reserved client number already exists.');return
        client=admin.call('/api/v1/validation/clients',{'name':NAME,'client_number':CLIENT})
        targets=sorted(set([*(f'admin{i:02d}@freshfields.example' for i in range(1,4)),*(f'conflicts{i:02d}@freshfields.example' for i in range(1,4)),*(f'lawyer{i:02d}@freshfields.example' for i in range(1,4)),settings['KESTREL_SUMEET_EMAIL'].casefold(),owner]))
        matters={}
        for number,label in [('100001','Alpha — wall checker lab'),('100002','Beta — wall checker lab')]:
            matter=admin.call('/api/v1/validation/matters',{'client_id':client['id'],'matter_number':number,'name':label});matters[number]=matter['id'];revision=1
            admin.call('/api/v1/validation/matters/'+matter['id']+'/decision',{'status':'validated','expected_revision':revision,'rationale':'Isolated synthetic security-checker lab; not part of Project Kestrel diligence coverage'});revision+=1
            for username in targets:
                if username==owner:continue
                admin.call('/api/v1/validation/matters/'+matter['id']+'/access',{'username':username,'assigned':True,'blocked':False,'days':365,'expected_revision':revision,'rationale':'One-time synthetic policy-checker fixture assignment; no existing main-matter grant changed'});revision+=1
        conflicts=LocalAPI('admin.localhost','conflicts01@freshfields.example',password);apis.append(conflicts)
        control_ids=[]
        for payload in [
            {'entry_type':'restriction','username':'lawyer03@freshfields.example'},
            {'entry_type':'restriction','username':'lawyer02@freshfields.example','matter_number':'100002'},
            {'entry_type':'relationship','username':'lawyer01@freshfields.example','relationship_kind':'relationship_partner'}]:
            row=admin.call('/api/v1/wall-checker/controls',{'client_number':CLIENT,'days':None,'rationale':'Synthetic fixture only: illustrate client inheritance, matter-only denial or a neutral relationship; not real professional clearance',**payload})
            conflicts.call('/api/v1/wall-checker/controls/'+row['id']+'/approve',{'rationale':'Separate fictional Conflicts profile approves this isolated test fixture; no real enterprise or legal clearance is implied'});control_ids.append(row['id'])
        lawyer=LocalAPI('firm.localhost','lawyer01@freshfields.example',password);apis.append(lawyer)
        sources={}
        for key,name,body in [
            ('WALLDEMO_OPEN','ordinary_contract.txt','Synthetic wall-checker example. The supplier requires written consent before assignment. This ordinary document has no specific AI restriction.'),
            ('WALLDEMO_NOAI','restricted_processing_contract.txt','Synthetic wall-checker example. No AI processing. This document may be read by cleared lawyers but its text must not be sent to an AI provider.')]:
            (folder/name).write_text(body,encoding='utf-8')
            query=urlencode({'matter_id':matters['100001'],'file_name':name,'logical_key':key,'classification':'ordinary','resource_type':'contract','language':'en','governing_law':'unconfirmed','wave':'manual','synthetic':'true'})
            source=lawyer.call('/api/v1/workflow/documents?'+query,binary=body.encode())
            lawyer.call('/api/v1/workflow/documents/'+source['id']+'/confirm',{'snapshot_hash':source['snapshot_hash'],'rationale':'Synthetic lab intake confirmation; no finding or publication approval'})
            sources[key]=source['id']
        checks={}
        for username,matter in [('lawyer03@freshfields.example','100001'),('lawyer02@freshfields.example','100002'),('lawyer02@freshfields.example','100001')]:
            result=admin.call('/api/v1/wall-checker/check',{'client_number':CLIENT,'matter_number':matter,'username':username,'action':'read'})
            checks[username+' / '+matter]=result['person']['eligible']
        assert list(checks.values())==[False,False,True]
        matrix=admin.call('/api/v1/wall-checker/check',{'client_number':CLIENT,'matter_number':'100001','username':'lawyer01@freshfields.example','action':'analyze','document_version_ids':list(sources.values())})
        assert [d['allowed'] for d in matrix['documents']]==[True,False]
        marker.write_text(json.dumps({'seeded':True,'client_number':CLIENT,'client_id':client['id'],'matters':matters,'control_ids':control_ids,'source_ids':sources,'person_checks':checks,'document_matrix':[d['allowed'] for d in matrix['documents']]},indent=2),encoding='utf-8')
        print('Wall checker lab initialized: client-wide block, matter-only block and mixed document ABAC; main matter and Wave 2 unchanged.')
    finally:
        for api in apis:
            try:api.close()
            except Exception:pass
if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('wall_checker_lab.failed',component='provisioning',exception=error);print('Wall lab initialization needs review; sanitized diagnostic '+event['event_id']);sys.exit(1)
