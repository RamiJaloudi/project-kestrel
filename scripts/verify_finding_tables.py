"""Normal-session, read-only finding query/detail/export checks; no legal decisions."""
import csv
import hashlib
import http.client
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from kestrel.localenv import read_env
from verify_report_connections import Session,CONTEXT


def main():
    sessions=[]
    try:
        password=read_env()['KESTREL_DUMMY_PASSWORD']
        firm=Session('firm.localhost','sme01@freshfields.example',password);sessions.append(firm)
        status,matters=firm.request('GET','/api/v1/workflow/matters');assert status==200
        matter=next(m['id'] for m in matters if m['client_number']=='012345' and m['matter_number']=='789012')
        payload={'matter_id':matter,'draw':3,'length':2,'sort':'summary','finding_filters':{'status':'all','register':'all'}}
        status,grid=firm.request('POST','/api/v1/tables/findings/query',payload)
        assert status==200 and grid['draw']==3 and grid['recordsTotal']>=len(grid['data'])
        rows=grid['data'];assert all('evidence' not in r and 'rationale' not in r and r['revision_id'] for r in rows)
        status,empty=firm.request('POST','/api/v1/tables/findings/query',{**payload,'search':'absent-legal-finding-81d6f1'})
        assert status==200 and empty['recordsFiltered']==0 and empty['recordsTotal']==grid['recordsTotal']
        status,consents=firm.request('POST','/api/v1/tables/findings/query',{**payload,'finding_filters':{'register':'consents','status':'all'}})
        assert status==200 and all(r['review_state']=='reviewed' and r['topic'] in {'change_of_control','assignment','termination'} for r in consents['data'])
        export_counts={};profile_available=None
        if rows:
            row=rows[0];query=urlencode({'matter_id':matter,'revision_id':row['revision_id'],'historical':'false'})
            status,detail=firm.request('GET','/api/v1/tables/findings/'+row['id']+'?'+query)
            assert status==200 and detail['finding']['revision_id']==row['revision_id'] and detail['finding']['source_id']==row['source_id']
            assert isinstance(detail['can_edit'],bool) and detail['finding']['evidence']
            profile_available=detail['source_review_available']
            status,_=firm.request('GET','/api/v1/tables/findings/'+row['id']+'?'+urlencode({'matter_id':matter,'revision_id':'not-the-selected-revision'}));assert status==409
            for fmt in ['csv','xlsx']:
                connection=http.client.HTTPSConnection('localhost',8443,context=CONTEXT,timeout=30)
                body={'matter_id':matter,'ids':[row['id']],'finding_versions':{row['id']:row['revision_id']},'format':fmt}
                connection.request('POST','/api/v1/tables/findings/export',body=json.dumps(body),headers={'Host':firm.host+':8443','Origin':'https://'+firm.host+':8443','Cookie':firm.cookie,'X-CSRF-Token':firm.csrf,'Content-Type':'application/json'})
                response=connection.getresponse();content=response.read();assert response.status==200
                unavailable=int(response.getheader('X-Export-Unavailable-Count'));assert unavailable in {0,1}
                assert response.getheader('X-Content-SHA256')==hashlib.sha256(content).hexdigest();connection.close()
                if fmt=='csv':
                    records=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))));assert len(records)==1-unavailable
                    if records:assert records[0]['id']==row['id'] and records[0]['revision_id']==row['revision_id']
                else:
                    from openpyxl import load_workbook
                    book=load_workbook(io.BytesIO(content));assert book.active.max_row==2-unavailable and all(c.data_type!='f' for cells in book.active for c in cells);book.close()
                export_counts[fmt]={'included':1-unavailable,'unavailable':unavailable}
        for host,user in [('firm.localhost','admin01@freshfields.example'),('bank.localhost','bank01@castlegate.example')]:
            session=Session(host,user,password);sessions.append(session)
            status,_=session.request('POST','/api/v1/tables/findings/query',payload);assert status==403
        report={'verified':True,'permitted_total':grid['recordsTotal'],'returned':len(rows),'empty_search':True,'consent_preset':True,'exact_detail_checked':bool(rows),'source_review_projection_available':profile_available,'export_counts':export_counts,'root_and_bank_denied':True,'business_decisions':0,'paid_calls':0}
        (ROOT/'.runtime/finding-tables-live-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
    finally:
        for session in sessions:
            status,_=session.request('POST','/api/v1/auth/logout',{});assert status==204


if __name__=='__main__':main()
