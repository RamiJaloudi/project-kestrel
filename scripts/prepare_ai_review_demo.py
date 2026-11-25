"""Install synthetic eight-risk demo governance without altering historical legal results."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env
from local_api import LocalAPI

def main():
    marker=root/'.runtime/ai-review-v2.json'
    if marker.exists():print('Eight-risk demo governance already prepared; existing approvals preserved.');return
    wave=json.loads((root/'.runtime/wave1-seeded.json').read_text());settings=read_env();password=settings['KESTREL_DUMMY_PASSWORD'];clients=[]
    def user(host,name):
        api=LocalAPI(host,name,password);clients.append(api);return api
    admin=user('admin.localhost','admin01@freshfields.example');sme=user('firm.localhost','sme01@freshfields.example');security=user('firm.localhost','security01@freshfields.example')
    try:
        existing=admin.call('/api/v1/policy-editor?matter_id='+wave['matter_id'])
        legal=json.loads((root/'data/playbooks/contract_risk_en_de_v2.json').read_text(encoding='utf-8'))
        definitions=[('Synthetic bilingual eight-risk review v2','legal_playbook',legal,sme),
            ('Personal synthetic OpenAI processing v2','environment_policy',{'block_ai':False,'block_cloud':False,'block_external':False,'allowed_regions':['OTHER']},security)]
        created={}
        for name,kind,definition,reviewer in definitions:
            if any(v['name']==name for v in existing):raise ValueError('Partial prior setup requires review; no approvals replayed')
            row=admin.call('/api/v1/policy-editor',{'matter_id':wave['matter_id'],'kind':kind,'name':name,'definition':definition});path='/api/v1/policy-editor/'+row['id']
            if kind=='legal_playbook':assert admin.call(path+'/test',{})['passed']
            admin.call(path+'/submit',{'expected_revision':1,'rationale':'Synthetic fixture requests separate-role review; no real legal clearance asserted'})
            reviewer.call(path+'/approve',{'expected_revision':2,'rationale':'Independent demo-role approval for fictional synthetic processing only'})
            admin.call(path+'/publish',{'expected_revision':3,'rationale':'Publish exact separately approved synthetic demo version'})
            created[kind]=row['id']
        replacements=[]
        for old in existing:
            if old['kind']=='environment_policy' and old['state']=='published' and old['name']=='Synthetic local processing policy':
                if old['definition']!={'block_ai':False,'block_cloud':True,'block_external':False,'allowed_regions':['OTHER']}:raise ValueError('Seed processing policy differs; explicit review required')
                request=admin.call('/api/v1/processing-policy',{'old_id':old['id'],'new_id':created['environment_policy'],'rationale':'Replace synthetic local-only policy with approved personal-demo processing. No real firm/client data or EU enterprise endpoint is asserted.'})
                security.call('/api/v1/processing-policy/'+request['id']+'/approve',{'rationale':'Separate Security demo identity approves this replacement for synthetic data only; no live job is automatically started.'})
                replacements.append(request['id'])
        marker.write_text(json.dumps({'matter_id':wave['matter_id'],'playbook_id':created['legal_playbook'],'processing_policy_id':created['environment_policy'],'replacement_ids':replacements},indent=2))
        print('Eight-risk synthetic playbook and personal-demo processing policy prepared with separate recorded demo-role approvals. No paid analysis was started.')
    finally:
        for api in clients:
            try:api.close()
            except Exception:pass
if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        event=emit('ai_demo.prepare.failed',component='provisioning',exception=error);print('AI preparation failed; sanitized diagnostic '+event['event_id']);sys.exit(1)
