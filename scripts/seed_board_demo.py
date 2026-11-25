"""One-time synthetic board fixture through normal lawyer HTTPS sessions; no grant restoration."""
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env
from kestrel.database import factory,make_engine,database_url
from kestrel.models import LegalFindingRevision,DocumentReviewVersion
from sqlalchemy import select
from local_api import LocalAPI

def main():
    marker=root/'.runtime/board-demo-seeded.json'
    if marker.exists():print('Board fixture already initialized; lawyer decisions remain unchanged.');return
    wave=root/'.runtime/wave1-seeded.json'
    if not wave.exists():return
    data=json.loads(wave.read_text());settings=read_env();engine=make_engine(database_url())
    with factory(engine)() as db:
        if db.scalar(select(LegalFindingRevision.id).limit(1)) or db.scalar(select(DocumentReviewVersion.id).limit(1)):
            print('Existing lawyer assessments detected; board fixture skipped without changing them.')
            marker.write_text(json.dumps({'seeded':False,'reason':'existing lawyer work'}));return
    engine.dispose()
    api=LocalAPI('firm.localhost','lawyer01@freshfields.example',settings['KESTREL_DUMMY_PASSWORD'])
    try:
        board=api.call('/api/v1/diligence/board?matter_id='+data['matter_id'])
        visible={s['id'] for s in board['sources']}
        targets=[('C001','Orion customer services agreement','Orion Demo AG','customer'),('L001','German software licence','Larch Synthetic GmbH','licence')]
        for key,title,party,scope in targets:
            source_id=data['source_ids'][key]
            if source_id not in visible:continue
            source=api.call('/api/v1/workflow/documents/'+source_id)
            if not source['classification_confirmed']:
                api.call('/api/v1/workflow/documents/'+source_id+'/confirm',{'snapshot_hash':source['snapshot_hash'],'rationale':'Synthetic lawyer fixture confirms original intake for board workflow'})
            if key=='L001':
                unit=next(u for u in source['units'] if 'Ziffer 7.' in u['text'])
                me=api.call('/api/v1/auth/me')
                api.call('/api/v1/diligence/findings',{'source_id':source_id,'expected_revision':0,'decision':'reviewed',
                    'summary':'The licence requires prior written consent for a change of control of the licensor. Confirm transaction applicability before signing.',
                    'topic':'change_of_control','severity':'high','materiality':'material','exposure':'consent','workflow_status':'open',
                    'action':'Check the change-of-control definition and transaction structure; obtain consent or resolve the condition before signing.',
                    'owner_id':me['id'],'due_on':None,'rationale':'Illustrative lawyer-authored fixture based on the synthetic German licence; not real legal clearance.',
                    'evidence':[{'unit':unit['number'],'quote':unit['text'],'start':0}]})
            api.call('/api/v1/diligence/documents/'+source_id+'/reviews',{'expected_revision':0,'title':title,'counterparty':party,'scope':scope,
                'coverage_state':'complete' if key=='C001' else 'in_review',
                'rationale':'Synthetic whole-document customer review fixture; recorded engine findings were reviewed.' if key=='C001' else 'Synthetic licence review is ongoing; a consent issue needs follow-up.'})
        marker.write_text(json.dumps({'seeded':True,'matter_id':data['matter_id'],'wave2_imported':False},indent=2))
        print('Board fixture initialized: contract metadata, explicit coverage and a cited lawyer-owned licence risk. Previous releases and Wave 2 preserved.')
    finally:api.close()

if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        row=emit('board_seed.failed',component='provisioning',exception=error)
        print('Board fixture failed; inspect sanitized diagnostic '+row['event_id']);sys.exit(1)
