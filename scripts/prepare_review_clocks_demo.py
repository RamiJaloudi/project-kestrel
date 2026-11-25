"""Prepare unsubmitted SLA demo drafts only, using normal local HTTPS sign-in."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from verify_report_connections import Session
from kestrel.localenv import read_env


def main():
    password=read_env()['KESTREL_DUMMY_PASSWORD'];sessions=[]
    try:
        root=Session('firm.localhost','admin01@freshfields.example',password);sessions.append(root)
        code,matters=root.request('GET','/api/v1/workflow/matters');assert code==200
        matter=next(m['id'] for m in matters if m['client_number']=='012345' and m['matter_number']=='789012')
        code,config=root.request('GET','/api/v1/review-clocks/configuration?matter_id='+matter);assert code==200
        calendar=next((c for c in config['calendars'] if c['name']=='London demo workweek'),None)
        if calendar is None:
            code,calendar=root.request('POST','/api/v1/review-clocks/calendars',{'matter_id':matter,'name':'London demo workweek','expected_previous_version':0,'timezone':'Europe/London','weekdays':[0,1,2,3,4],'holidays':[],'start_minute':540,'end_minute':1020});assert code==201
        policy=next((p for p in config['policies'] if p['name']=='Five-day demo review budget'),None)
        if policy is None:
            code,policy=root.request('POST','/api/v1/review-clocks/policies',{'matter_id':matter,'calendar_id':calendar['id'],'name':'Five-day demo review budget','stage':'review','expected_previous_version':0,'max_business_seconds':144000,'exclude_paused':True,'idle_timeout_seconds':300});assert code==201
        report={'verified':True,'matter_id':matter,'calendar_id':calendar['id'],'policy_id':policy['id'],'retained_policy_state':policy['state'],'approval_actions':0,'task_bindings_created':0,'paid_calls':0}
        (ROOT/'.runtime/review-clocks-demo.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
    finally:
        for s in sessions:
            code,_=s.request('POST','/api/v1/auth/logout',{})
            if code!=204:raise RuntimeError('Verification session cleanup failed')


if __name__=='__main__':main()
