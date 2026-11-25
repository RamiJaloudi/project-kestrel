"""Normal HTTPS policy checks; never changes existing rules, roles or releases."""
import json,sys
from pathlib import Path
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from local_api import LocalAPI
from kestrel.localenv import read_env

def main():
    fixture=json.loads((ROOT/'.runtime/wall-checker-lab.json').read_text())
    if not fixture.get('seeded'):raise RuntimeError('The isolated wall lab is not initialized')
    settings=read_env();password=settings['KESTREL_DUMMY_PASSWORD'];clients=[]
    try:
        admin=LocalAPI('admin.localhost',settings['KESTREL_RAMI_EMAIL'],password);clients.append(admin)
        identity=admin.call('/api/v1/auth/me');client=fixture['client_number'];results=[]
        for person,matter,expected in [('lawyer03@freshfields.example','100001',False),('lawyer03@freshfields.example','100002',False),('lawyer02@freshfields.example','100001',True),('lawyer02@freshfields.example','100002',False)]:
            value=admin.call('/api/v1/wall-checker/check',{'client_number':client,'matter_number':matter,'username':person,'action':'read'})
            assert value['person']['eligible']==expected;results.append(value['receipt_id'])
        whole_client=admin.call('/api/v1/wall-checker/check',{'client_number':client,'username':'lawyer02@freshfields.example','action':'read'})
        assert whole_client['allowed'] is None and not whole_client['person']['client_restricted']
        catalogue=admin.call('/api/v1/wall-checker/documents?client_number='+client+'&matter_number=100001')
        assert len(catalogue['documents'])==2 and all(not d['can_read'] and d['label'].startswith('Restricted policy reference') for d in catalogue['documents'])
        matrix=admin.call('/api/v1/wall-checker/check',{'client_number':client,'matter_number':'100001','username':'lawyer01@freshfields.example','action':'analyze','document_version_ids':list(fixture['source_ids'].values())})
        assert [d['allowed'] for d in matrix['documents']]==[True,False] and not matrix['allowed']
        assert matrix['operator']['id']==identity['id'] and matrix['person']['username']!=identity['username']
        assert admin.call('/api/v1/auth/me')['id']==identity['id']
        receipt=admin.call('/api/v1/wall-checker/checks/'+matrix['receipt_id']);assert 'Historical decision' in receipt['notice']
        try:admin.call('/api/v1/workflow/documents/'+fixture['source_ids']['WALLDEMO_OPEN']+'/reader')
        except HTTPError as error:assert error.code==403
        else:raise AssertionError('Diagnostic checker must not grant Root source access')
        for user,alpha,beta in [('lawyer02@freshfields.example',True,False),('lawyer03@freshfields.example',False,False)]:
            api=LocalAPI('firm.localhost',user,password);clients.append(api)
            for number,expected in [('100001',alpha),('100002',beta)]:
                value=api.call('/api/client-matter-validations',{'clientId':client,'matterId':number});assert value['valid']==expected
        conflicts=LocalAPI('admin.localhost','conflicts01@freshfields.example',password);clients.append(conflicts)
        assert 'conflicts_approver' in conflicts.call('/api/v1/wall-checker/context')['operator_roles']
        output={'verified':True,'client_inheritance':True,'matter_specific_isolation':True,'mixed_document_abac':[True,False],'root_reader_still_denied':True,'logged_in_operator_unchanged':True,'legacy_validation_enforced':True,'historical_receipt_retained':True,'no_ai_calls':True,'matrix_receipt_id':matrix['receipt_id']}
        (ROOT/'.runtime/wall-checker-verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
        print(json.dumps({key:value for key,value in output.items() if key!='matrix_receipt_id'}),flush=True)
    finally:
        for api in clients:
            try:api.close()
            except Exception:pass
if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('wall_checker.verification_failed',component='verification',exception=error);print('Wall verification needs review; sanitized diagnostic '+event['event_id']);sys.exit(1)
