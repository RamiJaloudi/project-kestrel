from fastapi import APIRouter,Depends,Response
from kestrel.api.auth import identity,database
from kestrel.schemas.disclosures import Plan,Review,Decision
from kestrel.services import disclosures as s,workflow as w
router=APIRouter(prefix='/api/v1/disclosures',tags=['Validated sanitized disclosures'])
@router.get('')
def listing(matter_id:str,actor=Depends(identity),db=Depends(database)):return s.listing(db,actor[2],matter_id)
@router.get('/plans')
def plans(source_id:str,actor=Depends(identity),db=Depends(database)):return s.plans(db,actor[2],source_id)
@router.post('/plans',status_code=201)
def propose(payload:Plan,actor=Depends(identity),db=Depends(database)):return s.propose(db,actor[2],payload)
@router.post('/plans/{plan_id}/review')
def review(plan_id:str,payload:Review,actor=Depends(identity),db=Depends(database)):return s.review_plan(db,actor[2],plan_id,payload)
@router.post('/plans/{plan_id}/build',status_code=201)
def build(plan_id:str,actor=Depends(identity),db=Depends(database)):return s.build(db,actor[2],plan_id)
@router.get('/artifacts/{artifact_id}')
def artifact(artifact_id:str,actor=Depends(identity),db=Depends(database)):
    a,p=s.read(db,actor[2],artifact_id);value=s.artifact_output(db,actor[2],a);w.event(db,actor[2],p,'disclosure.view',a.id);db.commit();return value
@router.get('/artifacts/{artifact_id}/reader')
def reader(artifact_id:str,actor=Depends(identity),db=Depends(database)):return s.reader(db,actor[2],artifact_id)
@router.get('/artifacts/{artifact_id}/download')
@router.get('/artifacts/{artifact_id}/inline')
def download(artifact_id:str,actor=Depends(identity),db=Depends(database)):
    a,p=s.read(db,actor[2],artifact_id);w.event(db,actor[2],p,'disclosure.binary',a.id);db.commit()
    return Response(a.data,media_type='application/pdf',headers={'Content-Disposition':'inline; filename="kestrel-disclosure-'+a.id+'.pdf"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"frame-ancestors 'self'",'X-Frame-Options':'SAMEORIGIN'})
@router.post('/artifacts/{artifact_id}/decisions')
def decide(artifact_id:str,payload:Decision,actor=Depends(identity),db=Depends(database)):return s.decide(db,actor[2],artifact_id,payload)
