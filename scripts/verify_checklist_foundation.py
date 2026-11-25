"""Read-only live checks; normal demo sessions, no approvals or paid AI."""
import json
from verify_report_connections import Session
from kestrel.localenv import read_env

def main():
    password=read_env()['KESTREL_DUMMY_PASSWORD'];sessions=[]
    try:
        root=Session('firm.localhost','admin01@freshfields.example',password);sessions.append(root)
        status,matters=root.request('GET','/api/v1/workflow/matters');assert status==200
        matter=next(m['id'] for m in matters if m['client_number']=='012345')
        status,versions=root.request('GET','/api/v1/checklists?matter_id='+matter);assert status==200 and versions
        row=versions[0]
        assert row['state']=='draft' and row['revision']==0
        assert len(row['definition']['sections'])==14
        assert row['definition']['items'][0]['item_id']=='KESTREL-G-CONTRACTS-001'
        assert row['definition']['items'][0]['source_item_number'] is None
        status,_=root.request('GET','/api/v1/checklists/'+row['id']+'/coverage');assert status==403
        sme=Session('firm.localhost','sme01@freshfields.example',password);sessions.append(sme)
        status,_=sme.request('GET','/api/v1/checklists/'+row['id']);assert status==200
        status,_=sme.request('GET','/api/v1/checklists/'+row['id']+'/coverage');assert status==409
        client=Session('client.localhost','client01@halden.example',password);sessions.append(client)
        status,_=client.request('GET','/api/v1/checklists/'+row['id']);assert status==403
        print(json.dumps({'verified':True,'sections':14,'original_requests':1,'draft_state':'unsubmitted_unapproved','root_coverage_denied':True,'unpublished_coverage_blocked':True,'external_denied':True,'paid_calls':0,'approval_actions':0}))
    finally:
        for session in sessions:
            code,_=session.request('POST','/api/v1/auth/logout',{})
            if code!=204:raise RuntimeError('Verification session cleanup failed')
if __name__=='__main__':main()
