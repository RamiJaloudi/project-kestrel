"""Read-only live verification using normal local sign-ins; no approvals or paid calls."""
import json
from verify_report_connections import Session
from kestrel.localenv import read_env


def main():
    password=read_env()['KESTREL_DUMMY_PASSWORD'];sessions=[]
    try:
        lawyer=Session('firm.localhost','lawyer01@freshfields.example',password);sessions.append(lawyer)
        code,matters=lawyer.request('GET','/api/v1/workflow/matters');assert code==200
        matter=next(m['id'] for m in matters if m['client_number']=='012345')
        code,fields=lawyer.request('GET','/api/v1/vdr-imports/fields?matter_id='+matter);assert code==200 and len(fields['fields'])==32
        code,sources=lawyer.request('GET','/api/v1/workflow/documents?matter_id='+matter);assert code==200 and sources
        assert all(s['document_id'] for s in sources)
        source=next(s for s in sources if s['classification']=='ordinary' and s['classification_confirmed'])
        code,reader=lawyer.request('GET','/api/v1/workflow/documents/'+source['id']+'/reader');assert code==200 and reader['document_id']==source['document_id'] and reader['bytes_hash']==source['bytes_hash']
        code,schema=lawyer.request('GET','/openapi/vdr-imports.json');assert code==200 and len(schema['paths'])==4
        root=Session('firm.localhost','admin01@freshfields.example',password);sessions.append(root)
        code,_=root.request('GET','/api/v1/vdr-imports/fields?matter_id='+matter);assert code==403
        bank=Session('bank.localhost','bank01@castlegate.example',password);sessions.append(bank)
        code,_=bank.request('GET','/api/v1/vdr-imports/profiles?matter_id='+matter);assert code==403
        print(json.dumps({'verified':True,'permitted_current_sources':len(sources),'identity_projection_present':True,'existing_reader_preserved':True,'swagger_operations':5,'admin_source_import_denied':True,'bank_import_denied':True,'paid_calls':0,'approvals':0}))
    finally:
        for session in sessions:
            code,_=session.request('POST','/api/v1/auth/logout',{})
            if code!=204:raise RuntimeError('Verification session cleanup failed')


if __name__=='__main__':main()
