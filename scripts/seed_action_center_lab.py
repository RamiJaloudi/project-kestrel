"""One-time synthetic impact walkthrough; preserves the main matter and Wave 2."""
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from local_api import LocalAPI
from kestrel.localenv import read_env


def wait(check):
    until=time.monotonic()+35
    while time.monotonic()<until:
        value=check()
        if value:return value
        time.sleep(.5)
    raise RuntimeError('Synthetic workflow did not become ready; inspect retained worker diagnostics')


def publish(admin,reviewer,matter,name,kind,definition,base=None):
    version=admin.call('/api/v1/policy-editor',{'matter_id':matter,'kind':kind,'name':name,'definition':definition,'base_playbook_id':base})
    path='/api/v1/policy-editor/'+version['id']
    if kind=='legal_playbook':
        assert admin.call(path+'/test',{})['passed']
    admin.call(path+'/submit',{'expected_revision':1,'rationale':'Scripted synthetic lab submission; not real legal clearance'})
    reviewer.call(path+'/approve',{'expected_revision':2,'rationale':'Separate synthetic role verifies this exact lab definition'})
    admin.call(path+'/publish',{'expected_revision':3,'rationale':'Publish isolated synthetic lab configuration'})
    return version['id']


def main():
    marker=ROOT/'.runtime/action-center-lab.json'
    if marker.exists():print('Action Center lab already initialized; existing task decisions preserved.');return
    values=read_env();password=values['KESTREL_DUMMY_PASSWORD'];owner=values['KESTREL_RAMI_EMAIL'].casefold();apis=[]
    folder=ROOT.parent/'Synthetic_Data/Action_Center_Lab';folder.mkdir(parents=True,exist_ok=True)
    def client(host,name):
        api=LocalAPI(host,name,password);apis.append(api);return api
    try:
        admin=client('admin.localhost',owner)
        if any(c['client_number']=='054322' for c in admin.call('/api/v1/validation/clients')):
            marker.write_text(json.dumps({'seeded':False,'reason':'Reserved client already exists; no partial fixture replay or access restoration'}),encoding='utf-8')
            print('Action Center lab reserved client already exists; existing records left unchanged.');return
        registry=admin.call('/api/v1/validation/clients',{'name':'Change-impact workflow lab (synthetic)','client_number':'054322'})
        matter=admin.call('/api/v1/validation/matters',{'client_id':registry['id'],'matter_number':'100001','name':'Action Center walkthrough — synthetic only'})['id']
        admin.call('/api/v1/validation/matters/'+matter+'/decision',{'status':'validated','expected_revision':1,'rationale':'Isolated synthetic Action Center walkthrough, separate from main diligence coverage'})
        usernames=sorted(set([*(f'sme{i:02d}@freshfields.example' for i in range(1,4)),'lawyer01@freshfields.example','security01@freshfields.example',values['KESTREL_CHRIS_EMAIL'].casefold()]))
        revision=2
        for username in usernames:
            admin.call('/api/v1/validation/matters/'+matter+'/access',{'username':username,'assigned':True,'blocked':False,'days':365,'expected_revision':revision,'rationale':'One-time isolated synthetic impact-lab assignment; does not amend existing main-matter access'})
            revision+=1
        lawyer=client('firm.localhost','lawyer01@freshfields.example')
        sme=client('firm.localhost','sme01@freshfields.example')
        independent=client('firm.localhost','sme02@freshfields.example')
        security=client('firm.localhost','security01@freshfields.example')
        publish(admin,security,matter,'Action Center lab offline processing','environment_policy',{'block_ai':False,'block_cloud':True,'block_external':False,'allowed_regions':['OTHER']})
        definition=json.loads((ROOT/'data/playbooks/PB-STARTER-GOVERNED-DRAFT.json').read_text(encoding='utf-8'))
        base=publish(admin,sme,matter,'Action Center lab playbook','legal_playbook',definition)
        sources={};findings={}
        texts={
            'A':'Synthetic contract A. A change of control requires prior written consent. Assignment requires prior written consent. Governing law: England and Wales.',
            'B':'Synthetic contract B. Assignment requires prior written consent. A change of control requires notification. Governing law: England and Wales.'}
        for key,body in texts.items():
            name='impact_lab_'+key+'.txt';(folder/name).write_text(body,encoding='utf-8')
            query=urlencode({'matter_id':matter,'file_name':name,'logical_key':'IMPACT-LAB-'+key,'classification':'ordinary','resource_type':'contract','language':'en','governing_law':'England and Wales','wave':'manual','synthetic':'true'})
            source=lawyer.call('/api/v1/workflow/documents?'+query,binary=body.encode())
            lawyer.call('/api/v1/workflow/documents/'+source['id']+'/confirm',{'snapshot_hash':source['snapshot_hash'],'rationale':'Scripted synthetic lab confirms original source handling'})
            job=sme.call('/api/v1/jobs',{'playbook_id':base,'document_version_id':source['id'],'idempotency_key':'impact-lab-first-'+key,'rationale':'Explicit offline first analysis for isolated lab'})
            wait(lambda:sme.call('/api/v1/jobs/'+job['id'])['state']=='succeeded')
            rows=[r for r in lawyer.call('/api/v1/workflow/findings?matter_id='+matter) if r['source_id']==source['id']]
            assert rows
            for finding in rows:lawyer.call('/api/v1/workflow/findings/'+finding['id']+'/review',{'decision':'reviewed','rationale':'Scripted synthetic lawyer profile verifies exact fixture evidence; not real advice'})
            sources[key]=source['id'];findings[key]=[r['id'] for r in rows]
        release=lawyer.call('/api/v1/workflow/releases',{'matter_id':matter,'audience':'halden','title':'Synthetic historical consent note','summary':'Synthetic lab: consent and notification require lawyer follow-up. This package is retained to demonstrate change-impact history.','references':[{'finding_id':f,'public_reference':'Synthetic contract A, consent clause'} for f in findings['A']]})
        independent.call('/api/v1/workflow/releases/'+release['id']+'/approve',{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],'rationale':'Independent scripted fixture release approval; synthetic role exercise only'})
        definition['rules'][0]['description']+=' Revised lab guidance: compare prior written consent with notification-only wording; retain the exact source passage.'
        target=publish(admin,sme,matter,'Action Center lab revised playbook','legal_playbook',definition,base)
        tasks=wait(lambda:([t for t in sme.call('/api/v1/action-center/tasks?matter_id='+matter) if t['target_id']==target]) or None)
        assert len(tasks)==2 and all(t['state']=='open' and t['job_id'] is None for t in tasks)
        marker.write_text(json.dumps({'seeded':True,'client_number':'054322','matter_id':matter,'base_playbook_id':base,'target_playbook_id':target,'sources':sources,'baseline_findings':findings,'historical_release_id':release['id'],'tasks':{t['source_id']:t['id'] for t in tasks}},indent=2),encoding='utf-8')
        print('Action Center lab ready: two open impact tasks, one historical released package, no rerun authorized. Main matter and Wave 2 unchanged.')
    finally:
        for api in apis:
            try:api.close()
            except Exception:pass


if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('action_center_lab.failed',component='provisioning',exception=error)
        print('Action Center fixture requires manual review; sanitized diagnostic '+event['event_id']);sys.exit(1)
