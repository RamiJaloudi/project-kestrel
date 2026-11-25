"""Explicit offline synthetic approval/review smoke test of lab B only."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from kestrel.localenv import read_env
from local_api import LocalAPI
from seed_action_center_lab import wait


def main():
    marker=ROOT/'.runtime/action-center-lab.json';lab=json.loads(marker.read_text(encoding='utf-8'))
    if not lab.get('seeded'):raise RuntimeError('Complete isolated lab required')
    if lab.get('verified_b'):print('Action Center lab B already verified; existing decisions unchanged.');return
    password=read_env()['KESTREL_DUMMY_PASSWORD']
    sme=LocalAPI('firm.localhost','sme01@freshfields.example',password)
    lawyer=LocalAPI('firm.localhost','lawyer01@freshfields.example',password)
    try:
        task_id=lab['tasks'][lab['sources']['B']];path='/api/v1/action-center/tasks/'+task_id
        task=sme.call(path)
        if task['state']!='open':raise RuntimeError('Lab B already has user decisions; do not replay fixture approvals')
        sme.call(path+'/claim',{})
        task=sme.call(path+'/approve',{'snapshot_hash':task['snapshot_hash'],'rationale':'Explicit synthetic offline smoke test approval for lab B only','idempotency_key':'action-center-lab-B-verification','engine_name':'literal'})
        task=wait(lambda:(lambda row:row if row['state']=='pending_attorney_review' else None)(sme.call(path)))
        assert task['comparisons']
        for comparison in task['comparisons']:
            finding=comparison['new']
            if finding:lawyer.call('/api/v1/workflow/findings/'+finding['id']+'/review',{'decision':'reviewed','rationale':'Scripted synthetic lawyer verifies exact cited passage in the retained lab source'})
            lawyer.call('/api/v1/action-center/comparisons/'+comparison['id']+'/disposition',{'disposition':'accept_reviewed_candidate' if finding else 'not_redetected_reviewed','rationale':'Scripted comparison retains prior records and separately reviews new fixture evidence'})
        result=lawyer.call(path+'/close',{'rationale':'Synthetic lab B rerun, evidence review and comparison verification completed','release_handling_rationale':''})
        assert result['state']=='closed'
        a=sme.call('/api/v1/action-center/tasks/'+lab['tasks'][lab['sources']['A']])
        assert a['state']=='open' and a['job_id'] is None and a['priority']=='urgent' and a['counts']['released_packages_visible']==1
        old=lawyer.call('/api/v1/workflow/releases/'+lab['historical_release_id'])
        assert old['released']
        for notice in sme.call('/api/v1/action-center/notifications'):
            if notice['task_id']==task_id:sme.call('/api/v1/action-center/notifications/'+notice['id']+'/resolve',{})
        lab['verified_b']=True;marker.write_text(json.dumps(lab,indent=2),encoding='utf-8')
        print('PASS: HTTPS-to-worker rerun, exact evidence, lawyer review, reconciliation and closure. Lab A stays open/urgent; historical release retained. No paid AI call.')
    finally:
        sme.close();lawyer.close()


if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('action_center_lab.verification_failed',component='verification',exception=error)
        print('Action Center verification needs manual review; sanitized diagnostic '+event['event_id']);sys.exit(1)
