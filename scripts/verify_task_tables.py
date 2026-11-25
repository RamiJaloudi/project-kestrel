"""Read-only authenticated local task-grid smoke checks; no assignment/approval writes."""
import csv
import http.client
import io
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from kestrel.localenv import read_env
from verify_report_connections import Session,CONTEXT


def main():
    sessions=[]
    try:
        password=read_env()['KESTREL_DUMMY_PASSWORD']
        firm=Session('firm.localhost','sme01@freshfields.example',password);sessions.append(firm)
        status,matters=firm.request('GET','/api/v1/workflow/matters');assert status==200
        matter=next(m['id'] for m in matters if m['client_number']=='012345' and m['matter_number']=='789012')
        payload={'matter_id':matter,'draw':7,'length':50,'sort':'file_name','direction':'asc','task_filters':{'historical':False}}
        status,grid=firm.request('POST','/api/v1/tables/tasks/query',payload)
        assert status==200 and grid['draw']==7 and grid['recordsTotal']>=len(grid['data'])
        rows=grid['data'];assert all(r['matter_id']==matter and 'rationale' not in r and 'events' not in r for r in rows)
        status,empty=firm.request('POST','/api/v1/tables/tasks/query',{**payload,'search':'nonexistent-task-81d72df1'})
        assert status==200 and empty['recordsFiltered']==0 and empty['recordsTotal']==grid['recordsTotal']
        export_counts={}
        if rows:
            status,filtered=firm.request('POST','/api/v1/tables/tasks/query',{**payload,'task_filters':{'stage':rows[0]['stage']}})
            assert status==200 and all(r['stage']==rows[0]['stage'] for r in filtered['data'])
            for fmt in ['csv','xlsx']:
                connection=http.client.HTTPSConnection('localhost',8443,context=CONTEXT,timeout=20)
                connection.request('POST','/api/v1/tables/tasks/export',body=json.dumps({'matter_id':matter,'ids':[rows[0]['id']],'format':fmt}),headers={'Host':firm.host+':8443','Origin':'https://'+firm.host+':8443','Cookie':firm.cookie,'X-CSRF-Token':firm.csrf,'Content-Type':'application/json'})
                response=connection.getresponse();content=response.read();assert response.status==200;unavailable=int(response.getheader('X-Export-Unavailable-Count'));assert unavailable in {0,1};export_counts[fmt]={'included':1-unavailable,'unavailable':unavailable};connection.close()
                if fmt=='csv':
                    records=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))));assert len(records)==1-unavailable and (not records or records[0]['id']==rows[0]['id'])
                else:
                    from openpyxl import load_workbook
                    book=load_workbook(io.BytesIO(content),data_only=False)
                    assert book.active.max_row==2-unavailable and all(c.data_type!='f' for row in book.active for c in row);book.close()
        for host,user in [('firm.localhost','admin01@freshfields.example'),('bank.localhost','bank01@castlegate.example')]:
            session=Session(host,user,password);sessions.append(session)
            status,_=session.request('POST','/api/v1/tables/tasks/query',payload);assert status==403
        report={'verified':True,'permitted_total':grid['recordsTotal'],'returned':len(rows),'empty_search':True,'typed_stage_filter':bool(rows),'csv_and_xlsx_checked':bool(rows),'export_counts':export_counts,'root_and_bank_denied':True,'assignment_changes':0,'approvals':0,'paid_calls':0}
        (ROOT/'.runtime/task-tables-live-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(report))
    finally:
        for session in sessions:
            status,_=session.request('POST','/api/v1/auth/logout',{});assert status==204


if __name__=='__main__':main()
