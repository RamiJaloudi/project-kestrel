"""Idempotent synthetic source-work fixture through normal HTTPS account sessions.

Creates coordination records only. No classifications, findings, approvals or AI jobs.
"""
import http.client,json,sys
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from verify_report_connections import Session,CONTEXT
from kestrel.localenv import read_env


def post(session,path,payload):
    status,value=session.request('POST',path,payload)
    if status not in {200,201}:raise RuntimeError('Synthetic coordination write denied')
    return value


def main():
    values=read_env();password=values['KESTREL_DUMMY_PASSWORD'];sessions=[]
    try:
        lawyer=Session('firm.localhost','lawyer01@freshfields.example',password);sessions.append(lawyer)
        sme=Session('firm.localhost','sme01@freshfields.example',password);sessions.append(sme)
        code,identity=sme.request('GET','/api/v1/auth/me');assert code==200
        code,matters=lawyer.request('GET','/api/v1/workflow/matters');assert code==200
        matter=next(m['id'] for m in matters if m['client_number']=='012345' and m['matter_number']=='789012')
        code,docs=lawyer.request('GET','/api/v1/workflow/documents?matter_id='+matter);assert code==200
        source=next((s for s in docs if s['logical_key']=='REVIEW-WORK-LAB-001'),None)
        if source is None:
            content=(ROOT/'synthetic/review-work-demo/coordination-contract.txt').read_bytes()
            params=urlencode({'matter_id':matter,'logical_key':'REVIEW-WORK-LAB-001','file_name':'coordination-contract.txt',
                'classification':'ordinary','resource_type':'contract','language':'en','wave':'manual','synthetic':'true'})
            connection=http.client.HTTPSConnection('localhost',8443,context=CONTEXT,timeout=15)
            connection.request('POST','/api/v1/workflow/documents?'+params,body=content,headers={'Host':lawyer.host+':8443','Origin':'https://'+lawyer.host+':8443','Cookie':lawyer.cookie,'X-CSRF-Token':lawyer.csrf,'Content-Type':'application/octet-stream'})
            response=connection.getresponse();raw=response.read();status=response.status;connection.close()
            if status!=201:raise RuntimeError('Synthetic source intake denied')
            source=json.loads(raw)
        sid=source['id'];base='/api/v1/review-work/sources/'+sid
        custodian1=post(lawyer,base+'/custodians',{'display_name':'Seller Legal Department','custodian_type':'department','custody_role':'origin','provenance':'Explicit synthetic vendor inventory in the fixture','request_key':'reviewlab-custodian-legal-001'})
        post(lawyer,base+'/custodians',{'display_name':'Transaction Records shared mailbox','custodian_type':'shared_mailbox','upn':'transaction-records@vireo.example','custody_role':'copy_holder','provenance':'Explicit synthetic vendor inventory in the fixture','request_key':'reviewlab-custodian-mailbox-002'})
        for name,role,key in [('Halden Example Holdings Ltd','buyer','reviewlab-party-buyer-001'),('Vireo Example Services GmbH','supplier','reviewlab-party-supplier-002')]:
            post(lawyer,base+'/parties',{'name':name,'party_role':role,'provenance':'Party names explicitly stated in synthetic source','request_key':key})
        code,lawyer_identity=lawyer.request('GET','/api/v1/auth/me');assert code==200
        t1=post(lawyer,base+'/tasks',{'stage':'review','assignee_id':lawyer_identity['id'],'request_key':'reviewlab-task-review-001','rationale':'Synthetic coordination fixture; no legal decision or approval'})
        t2=post(lawyer,base+'/tasks',{'stage':'qc','assignee_id':identity['id'],'request_key':'reviewlab-task-qc-002','rationale':'Independent synthetic QC coordination; no legal approval'})
        code,panel=lawyer.request('GET',base);assert code==200 and len(panel['custodians'])==2 and len(panel['parties'])==2 and len(panel['tasks'])==2
        code,notes=sme.request('GET','/api/v1/review-work/notifications?matter_id='+matter);assert code==200 and any(n['task_id']==t2['id'] for n in notes)
        for host,user in [('firm.localhost','admin01@freshfields.example'),('bank.localhost','bank01@castlegate.example')]:
            session=Session(host,user,password);sessions.append(session)
            code,_=session.request('GET',base);assert code==403
        report={'verified':True,'matter_id':matter,'source_id':sid,'document_id':source['document_id'],'custodians':2,'parties':2,
            'parallel_tasks':[t1['id'],t2['id']],'sme_notification_present':True,'root_and_bank_denied':True,'paid_calls':0,'approvals':0}
        (ROOT/'.runtime/review-work-demo.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(report))
    finally:
        for session in sessions:
            code,_=session.request('POST','/api/v1/auth/logout',{})
            if code!=204:raise RuntimeError('Verification session cleanup failed')


if __name__=='__main__':main()
