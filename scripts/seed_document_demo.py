"""One-time fictional fixture through real HTTPS APIs and the separate worker."""
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from sqlalchemy import select
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env
from kestrel.database import make_engine,database_url,factory
from kestrel.models import Account,MatterValidation,Client,MatterAssignment,CleanTeamMembership,SourceVersion
from kestrel.services.auth import clock,audit
from local_api import LocalAPI

def ensure_scopes(settings):
    with factory(make_engine(database_url()))() as db:
        matter=db.scalar(select(MatterValidation.matter_id).join(Client,Client.id==MatterValidation.client_id).where(Client.client_number=='012345',MatterValidation.matter_number=='789012'))
        if not matter:raise ValueError('Synthetic role-testing matter missing')
        for key in ['KESTREL_CHRIS_EMAIL','KESTREL_SUMEET_EMAIL']:
            account=db.scalar(select(Account).where(Account.username==settings[key].casefold()))
            if not db.scalar(select(MatterAssignment.id).where(MatterAssignment.account_id==account.id,MatterAssignment.matter_id==matter)):
                db.add(MatterAssignment(account_id=account.id,matter_id=matter,expires_at=clock()+30*86400));audit(db,'wave.fixture_scope','created',account.id,matter_id=matter)
        sme=db.scalar(select(Account).where(Account.username=='sme03@freshfields.example'))
        anti=db.scalar(select(Account).where(Account.username=='antitrust01@freshfields.example'))
        if not db.scalar(select(CleanTeamMembership.id).where(CleanTeamMembership.account_id==sme.id,CleanTeamMembership.matter_id==matter,CleanTeamMembership.scope=='pricing')):
            db.add(CleanTeamMembership(account_id=sme.id,matter_id=matter,scope='pricing',approved_by=anti.id,expires_at=clock()+30*86400))
            audit(db,'wave.fixture_clean_sme','created',sme.id,category='clean_team',matter_id=matter,clean_team_scope='pricing')
        db.commit();return matter

def main():
    settings=read_env();marker=root/'.runtime/wave1-seeded.json'
    if marker.exists():print('Wave 1 fixture already loaded; existing decisions and Wave 2 are unchanged.');return
    matter=ensure_scopes(settings)
    with factory(make_engine(database_url()))() as db:
        if db.scalar(select(SourceVersion.id).where(SourceVersion.matter_id==matter)):
            raise ValueError('Source data already exists; explicit seed-resume review required')
    password=settings['KESTREL_DUMMY_PASSWORD'];clients=[]
    def client(host,name):
        value=LocalAPI(host,name,password);clients.append(value);return value
    admin=client('admin.localhost','admin01@freshfields.example')
    sme=client('firm.localhost','sme01@freshfields.example')
    security=client('firm.localhost','security01@freshfields.example')
    lawyer=client('firm.localhost','lawyer01@freshfields.example')
    reviewer=client('firm.localhost','lawyer02@freshfields.example')
    clean=client('firm.localhost','cleanteam01@freshfields.example')
    try:
        definitions=[('Synthetic local processing policy','environment_policy',{
            'block_ai':False,'block_cloud':True,'block_external':False,'allowed_regions':['OTHER']},security),
            ('Synthetic bilingual consent spotting v1','legal_playbook',{
             'languages':['en','de'],'governing_laws':['unconfirmed','England and Wales','Germany'],
             'rules':[{'id':'COC','description':'Potential change of control clause for lawyer review','triggers':['change of control','Kontrollwechsel']},
                      {'id':'CONSENT','description':'Potential consent requirement for lawyer review','triggers':['prior written consent','Zustimmung']},
                      {'id':'ASSIGNMENT','description':'Potential assignment provision for lawyer review','triggers':['assignment','Abtretung']},
                      {'id':'PRICING','description':'Restricted pricing context requiring clean-team handling','triggers':['exclusive pricing']}],
             'test_cases':[{'text':'A change of control requires prior written consent for assignment.','expected_rule_ids':['COC','CONSENT','ASSIGNMENT']},
                           {'text':'Kontrollwechsel und Abtretung bedürfen der Zustimmung.','expected_rule_ids':['COC','CONSENT','ASSIGNMENT']},
                           {'text':'Routine delivery times are stated here.','expected_rule_ids':[]}],
             'authorities':[],'disclaimer':'Synthetic literal spotting fixture only; no legal conclusion or researched applicability.'},sme)]
        playbook=None
        for name,kind,definition,approver in definitions:
            draft=admin.call('/api/v1/policy-editor',{'matter_id':matter,'name':name,'kind':kind,'definition':definition})
            path='/api/v1/policy-editor/'+draft['id']
            if kind=='legal_playbook':assert admin.call(path+'/test',{})['passed']
            admin.call(path+'/submit',{'expected_revision':1,'rationale':'Synthetic operator fixture requests separate role approval'})
            approver.call(path+'/approve',{'expected_revision':2,'rationale':'Independent demo-role review of exact synthetic definition'})
            admin.call(path+'/publish',{'expected_revision':3,'rationale':'Publish exact role-approved synthetic fixture'})
            if kind=='legal_playbook':playbook=draft['id']
        folder=root/'data/synthetic_waves/Wave_1';manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        sources={}
        for item in manifest['documents']:
            data=(folder/item['file_name']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Fixture source checksum mismatch')
            params={k:item[k] for k in ['file_name','logical_key','classification','resource_type','language','governing_law','wave','clean_team_scope']}
            params.update(matter_id=matter,synthetic='true')
            actor=clean if item['classification']=='clean_team' else lawyer
            result=actor.call('/api/v1/workflow/documents?'+urlencode(params),binary=data)
            sources[item['logical_key']]=result
        contract=sources['C001']
        lawyer.call('/api/v1/workflow/documents/'+contract['id']+'/confirm',{'snapshot_hash':contract['snapshot_hash'],'rationale':'Synthetic fixture intake classification confirmed'})
        queued=sme.call('/api/v1/jobs',{'playbook_id':playbook,'document_version_id':contract['id'],'idempotency_key':'wave-one-contract-first-analysis','rationale':'Authorize synthetic first-wave source analysis'})
        for _ in range(40):
            status=sme.call('/api/v1/jobs/'+queued['id'])
            if status['state']=='succeeded':break
            if status['state'] in {'failed','denied'}:raise ValueError('Separate worker did not complete document analysis')
            time.sleep(1)
        else:raise ValueError('Document worker timeout')
        findings=lawyer.call('/api/v1/workflow/findings?matter_id='+matter)
        candidates=[f for f in findings if f['source_id']==contract['id']]
        for finding in candidates:
            lawyer.call('/api/v1/workflow/findings/'+finding['id']+'/review',{'decision':'reviewed','rationale':'Synthetic attorney-role check of exact original evidence and context'})
        packages=[]
        for audience in ['halden','castlegate']:
            release=lawyer.call('/api/v1/workflow/releases',{'matter_id':matter,'audience':audience,'title':'Wave 1 customer consent red flag',
                'summary':'The synthetic customer agreement contains consent and assignment wording. Counsel should check the transaction structure and any consent requirement before completion.',
                'references':[{'finding_id':candidates[0]['id'],'public_reference':'Synthetic customer agreement C001 version 1, clauses 9 and 12'}]})
            reviewer.call('/api/v1/workflow/releases/'+release['id']+'/approve',{'content_hash':release['content_hash'],'snapshot_hash':release['snapshot_hash'],
                'rationale':'Separate demo lawyer approves this exact audience-safe synthetic package'})
            packages.append(release['id'])
        for host,username in [('client.localhost','client01@halden.example'),('bank.localhost','bank01@castlegate.example')]:
            external=client(host,username)
            assert external.call('/api/v1/workflow/releases?matter_id='+matter)
        marker.write_text(json.dumps({'matter_id':matter,'source_ids':{k:v['id'] for k,v in sources.items()},'release_ids':packages,
            'clean_sme_username':'sme03@freshfields.example','playbook_id':playbook,'wave2_imported':False},indent=2),encoding='utf-8')
        print('Wave 1 loaded: five immutable sources, real worker findings, attorney review and two independent audience releases. Wave 2 remains local and unimported.')
    finally:
        for actor in clients:
            try:actor.close()
            except Exception:pass

if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        row=emit('wave_seed.failed',component='provisioning',exception=error)
        print('Wave fixture seed failed; inspect sanitized diagnostic '+row['event_id']);sys.exit(1)
