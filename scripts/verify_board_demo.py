"""Read-only smoke checks of the running, permission-filtered matter workspace."""
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from kestrel.localenv import read_env
from local_api import LocalAPI

def main():
    settings=read_env();wave=json.loads((root/'.runtime/wave1-seeded.json').read_text());password=settings['KESTREL_DUMMY_PASSWORD']
    path='/api/v1/diligence/board?matter_id='+wave['matter_id']
    api=LocalAPI('firm.localhost','lawyer01@freshfields.example',password)
    try:
        board=api.call(path)
        assert board['metrics']['received']==len(board['sources'])
        assert wave['source_ids']['P001'] not in {s['id'] for s in board['sources']}
        assert any(c['counterparty']=='Orion Demo AG' for c in board['contracts'])
        manual=next(f for f in board['findings'] if f['origin']=='lawyer')
        assert manual['evidence'] and manual['action'] and manual['owner_id']
        history=api.call('/api/v1/diligence/findings/'+manual['id']+'/history')
        assert history[-1]['revision_id']==manual['revision_id']
        print('PASS: real HTTPS board, contract/consent registers, lawyer-authored evidence and retained history verified.')
        print('Visible lawyer scope: '+json.dumps(board['metrics']))
    finally:api.close()
    for host,name in [('admin.localhost',settings['KESTREL_RAMI_EMAIL']),('client.localhost','client01@halden.example'),('bank.localhost','bank01@castlegate.example')]:
        api=LocalAPI(host,name,password)
        try:
            try:api.call(path)
            except HTTPError as error:assert error.code==403
            else:raise AssertionError('Internal board register must be denied')
        finally:api.close()
    print('PASS: Root Admin, ordinary Halden and Castlegate accounts cannot read internal board/register data.')

if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        row=emit('board_verification.failed',component='verification',exception=error)
        print('Board verification failed; sanitized diagnostic '+row['event_id']);sys.exit(1)
