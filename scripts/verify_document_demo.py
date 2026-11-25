"""Read-only business checks through real HTTPS sessions; no fixture decisions replayed."""
import json
import hashlib
from pathlib import Path
import sys
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from kestrel.localenv import read_env
from kestrel.database import database_url,make_engine,factory
from kestrel.models import SourceVersion,SourceFinding,ReleasePackage
from sqlalchemy import select,func
from local_api import LocalAPI

def verify():
    settings=read_env();marker=json.loads((ROOT/'.runtime/wave1-seeded.json').read_text())
    matter=marker['matter_id'];base='/api/v1/workflow';password=settings['KESTREL_DUMMY_PASSWORD']
    engine=make_engine(database_url())
    with factory(engine)() as db:
        # Report real state; do not assert a forever-empty Wave 2 after the operator uses it.
        counts={wave:db.scalar(select(func.count()).select_from(SourceVersion).where(SourceVersion.matter_id==matter,SourceVersion.wave==wave)) for wave in ['wave1','wave2']}
        candidates=db.scalar(select(func.count()).select_from(SourceFinding))
        packages=db.scalar(select(func.count()).select_from(ReleasePackage))
    engine.dispose()
    assert counts['wave1']>=5  # OCR produces a retained second source version.
    for host,user,audience in [('client.localhost','client01@halden.example','halden'),('bank.localhost','bank01@castlegate.example','castlegate')]:
        api=LocalAPI(host,user,password)
        try:
            rows=api.call(base+'/releases?matter_id='+matter)
            assert all(r['audience']==audience and r['released'] for r in rows)
            assert api.call(base+'/documents?matter_id='+matter)==[]
            try:api.call(base+'/documents/'+marker['source_ids']['C001'])
            except HTTPError as error:assert error.code==403
            else:raise AssertionError('External source access must be denied')
        finally:api.close()
    api=LocalAPI('admin.localhost',settings['KESTREL_RAMI_EMAIL'],password)
    try:
        assert api.call(base+'/documents?matter_id='+matter)==[]
        status=api.call(base+'/ai-status')
        assert status['run_limit_cents']==200 and status['month_limit_cents']==1000
    finally:api.close()
    api=LocalAPI('firm.localhost','lawyer01@freshfields.example',password)
    try:
        sources=api.call(base+'/documents?matter_id='+matter+'&historical=true')
        assert marker['source_ids']['C001'] in {r['id'] for r in sources}
        assert any(r['extraction_status']=='ocr_required' for r in sources)
        for key,kind in [('C001','pdf'),('L001','word'),('A001','word'),('S001','pdf')]:
            path=base+'/documents/'+marker['source_ids'][key]
            reader=api.call(path+'/reader?historical=true')
            assert reader['format']==kind and reader['units']
            if kind=='pdf':
                with api.opener.open(api.base+path+'/inline?historical=true',timeout=10) as response:
                    assert response.headers['Cache-Control']=='no-store'
                    assert response.headers['Content-Security-Policy']=="frame-ancestors 'self'"
                    assert hashlib.sha256(response.read()).hexdigest()==reader['bytes_hash']
        guides=api.call('/api/v1/resources')
        assert any(g['id']=='lawyer' and len(g['links'])==4 for g in guides)
    finally:api.close()
    api=LocalAPI('firm.localhost','cleanteam01@freshfields.example',password)
    try:
        reader=api.call(base+'/documents/'+marker['source_ids']['P001']+'/reader')
        assert reader['format']=='excel' and reader['sheets'][0]['rows']
    finally:api.close()
    print('PASS: real HTTPS audience isolation, no external/admin source override, OCR status, workflow links and USD 2/run + USD 10/month verified.')
    print('PASS: authenticated original PDF bytes, Word reader and named-scope Excel grid verified.')
    print('Retained state: '+json.dumps({'sources_by_wave':counts,'candidate_findings':candidates,'audience_packages':packages}))

if __name__=='__main__':
    try:verify()
    except Exception as error:
        from kestrel.diagnostics import emit
        row=emit('document_verification.failed',component='verification',exception=error)
        print('Document verification failed; sanitized diagnostic '+row['event_id']);sys.exit(1)
