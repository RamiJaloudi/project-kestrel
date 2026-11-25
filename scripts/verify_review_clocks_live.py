"""Verify local timing UI evidence; optional explicit pause of its synthetic coordination task."""
import argparse,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from verify_report_connections import Session
from kestrel.localenv import read_env


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pause-demo-task',action='store_true');args=parser.parse_args()
    fixture=json.loads((ROOT/'.runtime/review-work-demo.json').read_text());sessions=[];password=read_env()['KESTREL_DUMMY_PASSWORD']
    try:
        reviewer=Session('firm.localhost','lawyer01@freshfields.example',password);sessions.append(reviewer)
        tid=fixture['parallel_tasks'][0];code,task=reviewer.request('GET','/api/v1/review-work/tasks/'+tid);assert code==200
        if args.pause_demo_task and task['state']=='in_progress':
            code,task=reviewer.request('POST','/api/v1/review-work/tasks/'+tid+'/events',{'operation':'pause','expected_revision':task['revision'],
                'request_key':str(uuid4()),'rationale':'Synthetic timing UI check ended; pause coordination, no legal decision.'});assert code==201
        assert task['timing']['active_seconds'] is not None and task['timing']['active_seconds']>=0
        assert task['timing']['sla']['status']=='unconfigured'
        code,schema=reviewer.request('GET','/openapi/review-clocks.json');assert code==200 and len(schema['paths'])==8
        root=Session('firm.localhost','admin01@freshfields.example',password);sessions.append(root)
        code,_=root.request('GET','/api/v1/review-work/tasks/'+tid);assert code==403
        code,config=root.request('GET','/api/v1/review-clocks/configuration?matter_id='+fixture['matter_id']);assert code==200
        draft=next(p for p in config['policies'] if p['name']=='Five-day demo review budget')
        result={'verified':True,'demo_task_state':task['state'],'interaction_estimate_seconds':task['timing']['active_seconds'],
            'idle_observation_seconds':task['timing']['idle_seconds'],'unobserved_seconds':task['timing']['unobserved_seconds'],
            'sla_status':'unconfigured','retained_demo_policy_state':draft['state'],'root_task_access_denied':True,'swagger_operations':8,'approval_actions':0,'paid_calls':0}
        (ROOT/'.runtime/prompt-audit/review-clocks-live-verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
    finally:
        for s in sessions:
            code,_=s.request('POST','/api/v1/auth/logout',{})
            if code!=204:raise RuntimeError('Verification session cleanup failed')


if __name__=='__main__':main()
