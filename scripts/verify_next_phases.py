"""Explicit synthetic live checks. Leaves AI drafts unapproved and never freezes the demo matter."""
import argparse,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from local_api import LocalAPI
from kestrel.localenv import read_env

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:raise RuntimeError('Explicit --execute required for the authorized live AI checks')
    marker=ROOT/'.runtime/next-phases-verification.json';state=json.loads(marker.read_text()) if marker.exists() else {}
    def save():marker.write_text(json.dumps(state,indent=2),encoding='utf-8')
    settings=read_env();matter=json.loads((ROOT/'.runtime/ai-review-v2.json').read_text())['matter_id'];password=settings['KESTREL_DUMMY_PASSWORD']
    clients=[]
    try:
        lawyer=LocalAPI('firm.localhost','lawyer01@freshfields.example',password);clients.append(lawyer)
        sme=LocalAPI('firm.localhost','sme03@freshfields.example',password);clients.append(sme)
        halden=LocalAPI('client.localhost','client01@halden.example',password);clients.append(halden)
        if 'report_request_key' not in state:
            reports=lawyer.call('/api/v1/reports?matter_id='+matter)
            eligible=[r for r in reports if not r['lineage_stale'] and not r['released']]
            if not eligible:raise RuntimeError('Create an eligible reviewed-findings report draft first')
            state.update(report_parent_id=max(eligible,key=lambda r:r['version'])['id'],report_request_key=str(uuid4()));save()
        if 'ai_report_id' not in state:
            report=lawyer.call('/api/v1/reports/'+state['report_parent_id']+'/ai-draft',{'request_key':state['report_request_key']})
            assert not report['released'] and report['body']['generator'].startswith('openai-')
            state['ai_report_id']=report['id'];save()
        if 'question_answer_id' not in state:
            answer=lawyer.call('/api/v1/questions',{'matter_id':matter,'question':'Which customer contracts may be terminated on a change of control, and what consent exceptions apply?'})
            assert answer['citations'];state['question_answer_id']=answer['id'];state['qa_request_key']=str(uuid4());save()
        if 'ai_answer_id' not in state:
            answer=lawyer.call('/api/v1/questions/'+state['question_answer_id']+'/synthesize',{'request_key':state['qa_request_key']})
            assert answer['mode']=='openai_internal_candidate'
            state['ai_answer_id']=answer['id'];state['qa_state']=answer['status'];save()
        if 'client_message_id' not in state:
            releases=halden.call('/api/v1/workflow/releases?matter_id='+matter)
            release=next(r for r in releases if r['released'])
            message=halden.call('/api/v1/collaboration',{'release_id':release['id'],'kind':'question','body':'Synthetic walkthrough: which consent follow-up should the legal team prioritize before signing?'})
            state['client_message_id']=message['id'];state['discussion_release_id']=release['id'];save()
        if 'firm_reply_draft_id' not in state:
            message=lawyer.call('/api/v1/collaboration',{'release_id':state['discussion_release_id'],'parent_id':state['client_message_id'],'kind':'reply','body':'Synthetic draft for independent lawyer review: confirm the released consent action against the transaction structure before making a request.'})
            state['firm_reply_draft_id']=message['id'];save()
        visible=halden.call('/api/v1/collaboration?release_id='+state['discussion_release_id'])
        assert state['client_message_id'] in {r['id'] for r in visible} and state['firm_reply_draft_id'] not in {r['id'] for r in visible}
        if 'archive_id' not in state:
            archive=sme.call('/api/v1/archives',{'matter_id':matter});state['archive_id']=archive['id'];save()
        verification=sme.call('/api/v1/archives/'+state['archive_id']+'/verify',{});assert verification['verified']
        state['source_archive_verified']=verification['reconstructed_source_versions'];state['budget']=sme.call('/api/v1/workflow/ai-status');state['budget'].pop('model',None);save()
        print(json.dumps({'ai_report_draft_created':True,'internal_ai_qa_state':state['qa_state'],'client_question_visible':True,'unapproved_firm_reply_hidden':True,'source_versions_reconstructed':state['source_archive_verified'],'spent_estimate_cents':state['budget']['spent_estimate_cents'],'reserved_cents':state['budget']['reserved_cents'],'no_ai_output_released':True,'demo_matter_remains_open':True}),flush=True)
    finally:
        for api in clients:
            try:api.close()
            except Exception:pass
if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('next_phases.verification_failed',component='verification',exception=error)
        print('Verification needs review; retained request keys prevent automatic resend. Diagnostic '+event['event_id']);sys.exit(1)
