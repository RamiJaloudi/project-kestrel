"""Explicit paid synthetic verification. Each source can be requested once; reruns never resend a provider call."""
import argparse,hashlib,json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env
from kestrel.adapters.openai_review import configuration
from local_api import LocalAPI
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--only',choices=['AIEN','AIDE','AINO','SCANOCR','AIEN_HOLDOUT']);args=parser.parse_args()
    if not args.execute:raise SystemExit('Pass --execute for user-authorized paid synthetic checks.')
    enabled,key=configuration()
    if not enabled or not key:raise SystemExit('Provider is not configured and enabled. No paid call made.')
    settings=read_env();setup=json.loads((root/'.runtime/ai-review-v2.json').read_text());folder=root.parent/'Synthetic_Data/AI_Review_Lab'
    manifest=json.loads((folder/'evaluation_manifest.json').read_text());marker=root/'.runtime/live-ai-evaluation.json'
    results=json.loads(marker.read_text()) if marker.exists() else {'runs':{}}
    lawyer=LocalAPI('firm.localhost','lawyer01@freshfields.example',settings['KESTREL_DUMMY_PASSWORD']);sme=LocalAPI('firm.localhost','sme01@freshfields.example',settings['KESTREL_DUMMY_PASSWORD'])
    try:
        targets=manifest['documents'].copy()
        ocr=json.loads((root/'.runtime/ocr-live-demo.json').read_text());targets.append({'logical_key':'SCANOCR','source_id':ocr['source_id'],'expected_risks':['ASSIGNMENT']})
        if args.only:targets=[item for item in targets if item['logical_key']==args.only]
        for item in targets:
            tag=item['logical_key']
            if tag in results['runs'] and results['runs'][tag].get('state')=='succeeded':print(tag+': existing successful live result preserved.',flush=True);continue
            if 'source_id' in item:source=lawyer.call('/api/v1/workflow/documents/'+item['source_id'])
            else:
                body=(folder/item['file_name']).read_bytes();current=lawyer.call('/api/v1/workflow/documents?matter_id='+setup['matter_id']);old=next((s for s in current if s['logical_key']==tag),None)
                if old:
                    if old['bytes_hash']!=hashlib.sha256(body).hexdigest():raise RuntimeError('Evaluation source changed; explicit new version review required')
                    source=lawyer.call('/api/v1/workflow/documents/'+old['id'])
                else:
                    from urllib.parse import urlencode
                    params={'matter_id':setup['matter_id'],'file_name':item['file_name'],'logical_key':tag,'classification':'ordinary','resource_type':'contract','language':item['language'],'governing_law':'unconfirmed','wave':'manual','synthetic':'true'}
                    source=lawyer.call('/api/v1/workflow/documents?'+urlencode(params),binary=body)
                if not source['classification_confirmed']:lawyer.call('/api/v1/workflow/documents/'+source['id']+'/confirm',{'snapshot_hash':source['snapshot_hash'],'rationale':'Synthetic evaluation source handling confirmed; no model finding or release approval'})
            if tag not in results['runs']:
                job=sme.call('/api/v1/jobs',{'playbook_id':setup['playbook_id'],'document_version_id':source['id'],'engine_name':'openai','idempotency_key':'ai-v2-eval-'+source['id'],'rationale':'User-authorized first synthetic live review under USD 2/run and USD 10/month; candidates only, no external release'})
                results['runs'][tag]={'job_id':job['id'],'source_id':source['id'],'state':job['state']};marker.write_text(json.dumps(results,indent=2))
            print(tag+': waiting for authorized live worker review.',flush=True)
            for _ in range(90):
                job=sme.call('/api/v1/jobs/'+results['runs'][tag]['job_id'])
                if job['state'] in {'succeeded','failed','denied'}:break
                time.sleep(1)
            record=results['runs'][tag];record['state']=job['state'];record['error_code']=job.get('error_code')
            if job['state']!='succeeded':marker.write_text(json.dumps(results,indent=2));raise RuntimeError('Live review failed or is pending; do not automatically resend it')
            data=job['result'];found={f['rule_id'] for f in data['findings']};expected=set(item['expected_risks'])
            record.update(coverage=data.get('coverage',[]),found_rules=sorted(found),missing_expected_rules=sorted(expected-found),unexpected_rules=sorted(found-expected),windows=data.get('context_windows'))
            marker.write_text(json.dumps(results,indent=2));print(tag+': live review succeeded; '+str(len(found))+' cited risk groups; '+str(len(expected-found))+' expected groups missing.',flush=True)
        budget=sme.call('/api/v1/workflow/ai-status');results['budget']={k:budget[k] for k in ['period','spent_estimate_cents','reserved_cents','month_limit_cents']};marker.write_text(json.dumps(results,indent=2))
        print('Live evaluations retained; no findings were lawyer-approved or released. Application budget: '+json.dumps(results['budget']),flush=True)
    finally:
        for api in [lawyer,sme]:
            try:api.close()
            except Exception:pass
if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        row=emit('live_ai.verification.failed',component='verification',exception=error);print('Live verification needs review; sanitized diagnostic '+row['event_id']);sys.exit(1)
